"""Twinings/Ovaltine RAG ingestion powered by crawl4ai."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests
from bs4 import BeautifulSoup
from crawl4ai import (
    AsyncWebCrawler,
    CacheMode,
    CrawlerRunConfig,
    DefaultMarkdownGenerator,
    LinkPreviewConfig,
)
from duckduckgo_search import DDGS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv
from azure.ai.inference import EmbeddingsClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

logger = logging.getLogger("crawl_ingest")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FAISS_DIR = ROOT_DIR / "faiss_index"
INDEX_NAME = "index"

EMBEDDING_ENDPOINT = "https://llmaccess.services.ai.azure.com/models"
EMBEDDING_KEY = os.getenv("EMBEDDING_KEY", "").strip()
if not EMBEDDING_KEY:
    raise RuntimeError("EMBEDDING_KEY is not set in the environment")

EMBED_CLIENT = EmbeddingsClient(
    endpoint=EMBEDDING_ENDPOINT,
    credential=AzureKeyCredential(EMBEDDING_KEY)
)


class InlineAzureEmbeddings:
    """Minimal adapter so FAISS can request embeddings."""

    model_name = os.getenv("EMBEDDING_MODEL", "embed-v-4-0")
    batch_limit = int(os.getenv("EMBEDDING_BATCH_LIMIT", "90"))

    @staticmethod
    def embed_documents(texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        batch_size = max(1, InlineAzureEmbeddings.batch_limit)
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            for attempt in range(5):  # max retries
                try:
                    response = EMBED_CLIENT.embed(input=batch, model=InlineAzureEmbeddings.model_name)
                    vectors.extend(item.embedding for item in response.data)
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < 4:
                        wait_time = 2 ** attempt  # exponential backoff
                        logger.warning(f"Rate limit hit, waiting {wait_time} seconds")
                        time.sleep(wait_time)
                    else:
                        raise
        return vectors

    @staticmethod
    def embed_query(text: str) -> List[float]:
        return InlineAzureEmbeddings.embed_documents([text])[0]


SEED_URLS = [
    "https://en.wikipedia.org/wiki/Twinings",
    "https://en.wikipedia.org/wiki/Ovaltine",
    "https://www.twinings.co.uk/about-twinings/company-history",
    "https://www.twinings.co.uk/about-twinings/meet-the-team",
    "https://www.abf.co.uk/about_abf/our_history",
    "https://www.abf.co.uk/about_abf/our_businesses/ingredients/twinings_ovaltine",
    "https://www.associatedbritishfoodsplc.com/en/investors/shareholder-information",
    "https://www.ovaltine.co.uk/our-story",
]
ALLOWED_DOMAIN_SNIPPETS = [
    "wikipedia.org",
    "twinings.",
    "abf.co.uk",
    "associatedbritishfoods",
    "ovaltine.",
]
KEYWORD_FILTER = ["twinings", "ovaltine", "associated british", "abf", "wander"]
DEFAULT_DDG_QUERIES = [
    "Twinings Ovaltine heritage",
    "Twinings shareholder report",
    "Ovaltine sustainability pdf",
    "Associated British Foods Twinings filing",
    "Twinings annual report",
    "Ovaltine investors presentation",
    "Twinings history site:wikipedia.org",
    "Twinings heritage site:gov.uk",
    "Twinings Ovaltine CSR report",
    "Twinings stakeholder engagement pdf",
]
MAX_QUEUE_SIZE = int(os.getenv("CRAWL_MAX_QUEUE", "5000"))
MAX_PDF_BYTES = int(os.getenv("CRAWL_MAX_PDF_BYTES", str(8 * 1024 * 1024)))  # 8MB default
RAW_BINARY_DIR = RAW_DIR / "binary"
RAW_BINARY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class RawRecord:
    url: str
    title: str
    html: str
    markdown: str
    crawled_at: str
    links: List[str]

    def to_json(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "html": self.html,
            "markdown": self.markdown,
            "crawled_at": self.crawled_at,
            "links": self.links,
        }


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FAISS_DIR.mkdir(parents=True, exist_ok=True)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sanitize_text(html: str, markdown: str) -> str:
    if html:
        soup = BeautifulSoup(html, "lxml")
        for bad in soup.find_all(["script", "style", "noscript"]):
            bad.decompose()
        text = soup.get_text(" ", strip=True)
    else:
        text = markdown
    return collapse_whitespace(text)


def extract_links(link_blob: Any) -> List[str]:
    links: List[str] = []

    def append_all(items: Any) -> None:
        if not items:
            return
        for item in items:
            href = item.get("href") if isinstance(item, dict) else getattr(item, "href", None)
            if href:
                links.append(href)

    if isinstance(link_blob, dict):
        append_all(link_blob.get("internal"))
        append_all(link_blob.get("external"))
    else:
        append_all(getattr(link_blob, "internal", []))
        append_all(getattr(link_blob, "external", []))
    return links


def is_allowed_url(url: str) -> bool:
    if not url.startswith("http"):
        return False
    lower = url.lower()
    return any(s in lower for s in ALLOWED_DOMAIN_SNIPPETS) and any(k in lower for k in KEYWORD_FILTER)


def next_links(links: Sequence[str], seen: set[str], limit: int) -> List[str]:
    stack: List[str] = []
    for link in links:
        if len(stack) >= limit:
            break
        if link in seen:
            continue
        if is_allowed_url(link):
            stack.append(link)
    return stack


async def crawl(seed_urls: Sequence[str], max_pages: int, per_page_limit: int) -> List[RawRecord]:
    queue = list(dict.fromkeys(seed_urls))
    seen: set[str] = set()
    harvested: List[RawRecord] = []

    async with AsyncWebCrawler() as crawler:
        while queue and len(harvested) < max_pages:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            logger.info("Crawling %s", url)

            config = CrawlerRunConfig(
                link_preview_config=LinkPreviewConfig(
                    include_internal=True,
                    include_external=False,
                    max_links=20,
                    concurrency=3,
                    timeout=20,
                    query="Twinings Ovaltine heritage",
                ),
                cache_mode=CacheMode.ENABLED,
                screenshot=False,
                markdown_generator=DefaultMarkdownGenerator(),
                check_robots_txt=True,
            )

            try:
                run = await crawler.arun(url=url, config=config)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error crawling %s: %s", url, exc)
                continue

            result = getattr(run, "_results", [run])[0]
            html = getattr(result, "html", "") or ""
            markdown = ""
            if hasattr(result, "markdown") and result.markdown:
                markdown = getattr(result.markdown, "raw_markdown", str(result.markdown)) or ""

            meta = getattr(result, "metadata", {}) or {}
            title = meta.get("title") or meta.get("page_title") or "Unknown"
            links = extract_links(getattr(result, "links", None))

            harvested.append(
                RawRecord(
                    url=url,
                    title=title,
                    html=html,
                    markdown=markdown,
                    crawled_at=datetime.utcnow().isoformat(),
                    links=links,
                )
            )

            queue.extend(next_links(links, seen.union(queue), per_page_limit))

            if len(harvested) >= max_pages:
                break

    logger.info("Crawled %d pages", len(harvested))
    return harvested


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def clean(raw: Sequence[RawRecord]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for record in raw:
        text = sanitize_text(record.html, record.markdown)
        if not text:
            continue
        fingerprint = hash(text[:500])
        if fingerprint in seen_hashes:
            continue
        seen_hashes.add(fingerprint)
        cleaned.append(
            {
                "url": record.url,
                "title": record.title,
                "content": text,
                "crawled_at": record.crawled_at,
            }
        )
    logger.info("Cleaned to %d documents", len(cleaned))
    return cleaned


def chunk_docs(docs: Sequence[Dict[str, Any]], run_id: str, chunk: int, overlap: int) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " "]
    )
    pieces: List[Document] = []
    for doc in docs:
        splits = splitter.split_text(doc["content"])
        for idx, split in enumerate(splits):
            pieces.append(
                Document(
                    page_content=split,
                    metadata={
                        "source": doc["url"],
                        "title": doc["title"],
                        "run_id": run_id,
                        "chunk_index": idx,
                        "chunks_total": len(splits),
                        "crawled_at": doc["crawled_at"],
                    },
                )
            )
    logger.info("Built %d chunks", len(pieces))
    return pieces


def serialize_docs(path: Path, docs: Sequence[Document]) -> None:
    write_jsonl(path, ({"page_content": d.page_content, "metadata": d.metadata} for d in docs))


def backup_index(stamp: str) -> Optional[Path]:
    faiss_file = FAISS_DIR / f"{INDEX_NAME}.faiss"
    meta_file = FAISS_DIR / f"{INDEX_NAME}.pkl"
    if not faiss_file.exists() and not meta_file.exists():
        return None
    backup_dir = FAISS_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{INDEX_NAME}_{stamp}"
    target.mkdir(parents=True, exist_ok=True)
    if faiss_file.exists():
        shutil.copy2(faiss_file, target / faiss_file.name)
    if meta_file.exists():
        shutil.copy2(meta_file, target / meta_file.name)
    logger.info("Backed up FAISS index to %s", target)
    return target


def rebuild_index(documents: Sequence[Document], stamp: str) -> None:
    # Add specific knowledge about CEO
    ceo_doc = Document(
        page_content="The CEO of Twinings Ovaltine is Olav Silden.",
        metadata={
            "source": "manual_entry",
            "title": "CEO Information",
            "run_id": stamp,
            "chunk_index": 0,
            "chunks_total": 1,
            "crawled_at": datetime.utcnow().isoformat(),
        },
    )
    faiss_file = FAISS_DIR / f"{INDEX_NAME}.faiss"
    meta_file = FAISS_DIR / f"{INDEX_NAME}.pkl"
    if faiss_file.exists() and meta_file.exists():
        # Load existing and add CEO
        store = FAISS.load_local(str(FAISS_DIR), INDEX_NAME, allow_dangerous_deserialization=True)
        store.add_documents([ceo_doc])
        logger.info("Added CEO info to existing FAISS index")
    else:
        # Create new with documents + CEO
        all_documents = list(documents) + [ceo_doc]
        store = FAISS.from_documents(all_documents, InlineAzureEmbeddings())
        logger.info("Created new FAISS index with %d docs", len(all_documents))
    backup_index(stamp)
    store.save_local(str(FAISS_DIR), INDEX_NAME)
    logger.info("FAISS store saved")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Twinings/Ovaltine crawl4ai ingestion")
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--per-page-link-cap", type=int, default=10)
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--skip-crawl", action="store_true")
    parser.add_argument("--raw-path", type=str)
    parser.add_argument("--seed-file", type=str)
    parser.add_argument("--use-ddg", action="store_true", help="Use DuckDuckGo advanced search to expand seeds")
    parser.add_argument("--ddg-results", type=int, default=100, help="Results per DDG query")
    parser.add_argument("--include-pdfs", action="store_true", help="Attempt to fetch linked PDF investor documents")
    parser.add_argument("--target-mb", type=int, default=100, help="Target corpus size (MB) before stopping")
    parser.add_argument("--max-runtime-min", type=int, default=30, help="Safety limit for crawl duration (minutes)")
    parser.add_argument("--add-ceo-only", action="store_true", help="Only add CEO information to existing FAISS index without crawling")
    return parser.parse_args()


def load_seed_file(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Seed file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def hash_text(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()


def canonicalize_url(url: str) -> str:
    lowered = url.split("#")[0]
    return lowered.rstrip("/")


def run_ddg_queries(queries: Sequence[str], max_results: int) -> List[str]:
    ddg = DDGS()
    urls: List[str] = []
    for query in queries:
        try:
            for item in ddg.text(query, max_results=max_results, safesearch="off", region="wt-wt"):
                link = item.get("href") or item.get("url")
                if link:
                    urls.append(link)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DDG search failure for %s: %s", query, exc)
    return urls


def fetch_pdf(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        if "application/pdf" not in resp.headers.get("Content-Type", ""):
            return None
        if len(resp.content) > MAX_PDF_BYTES:
            logger.info("Skipping PDF over size limit: %s", url)
            return None
        from pdfminer.high_level import extract_text
        text = extract_text(io.BytesIO(resp.content))
        if text:
            pdf_hash = hash_text(url)
            pdf_path = RAW_BINARY_DIR / f"{pdf_hash}.pdf"
            with pdf_path.open("wb") as fh:
                fh.write(resp.content)
            return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch PDF %s: %s", url, exc)
    return None


def expand_seeds(base_seeds: List[str], ddg_queries: Sequence[str], ddg_results: int) -> List[str]:
    search_urls = run_ddg_queries(ddg_queries, ddg_results)
    combined = base_seeds + search_urls
    deduped = list(dict.fromkeys(combined))
    logger.info("Expanded seeds to %d URLs", len(deduped))
    return deduped[:MAX_QUEUE_SIZE]


async def main() -> None:
    args = parse_args()
    ensure_dirs()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    if not args.add_ceo_only:
        seeds = list(SEED_URLS)
        if args.seed_file:
            seeds.extend(load_seed_file(Path(args.seed_file)))
        if args.use_ddg:
            seeds = expand_seeds(seeds, DEFAULT_DDG_QUERIES, args.ddg_results)
        seeds = list(dict.fromkeys(seeds))

        start_time = datetime.utcnow().isoformat()

        raw_records: List[RawRecord] = []
        if args.skip_crawl:
            if not args.raw_path:
                raise ValueError("--raw-path required when using --skip-crawl")
            raw_items = load_jsonl(Path(args.raw_path))
            raw_records = [
                RawRecord(
                    url=item["url"],
                    title=item.get("title", "Unknown"),
                    html=item.get("html", ""),
                    markdown=item.get("markdown", ""),
                    crawled_at=item.get("crawled_at", run_id),
                    links=item.get("links", []),
                )
                for item in raw_items
            ]
            logger.info("Loaded %d raw records", len(raw_records))
        else:
            try:
                raw_records = await asyncio.wait_for(
                    crawl(seeds, max_pages=args.max_pages, per_page_limit=args.per_page_link_cap),
                    timeout=30 * 60  # 30 minutes in seconds
                )
            except asyncio.TimeoutError:
                logger.info("Crawl timed out after 30 minutes; proceeding with available data")
            if raw_records:
                raw_path = RAW_DIR / f"twinings_raw_{run_id}.jsonl"
                write_jsonl(raw_path, (record.to_json() for record in raw_records))
                logger.info("Saved raw crawl to %s", raw_path)

        if args.include_pdfs:
            for record in raw_records:
                pdf_text = fetch_pdf(record.url)
                if pdf_text:
                    record.markdown += "\n" + pdf_text

        cleaned_docs = clean(raw_records)
        clean_path = PROCESSED_DIR / f"twinings_clean_{run_id}.jsonl"
        write_jsonl(clean_path, cleaned_docs)
        logger.info("Saved cleaned docs to %s", clean_path)

        chunks = chunk_docs(cleaned_docs, run_id, args.chunk_size, args.chunk_overlap)
        chunk_path = PROCESSED_DIR / f"twinings_chunks_{run_id}.jsonl"
        serialize_docs(chunk_path, chunks)
        logger.info("Saved chunks to %s", chunk_path)

        rebuild_index(chunks, run_id)
    else:
        logger.info("Adding CEO information to existing index")
        rebuild_index([], run_id)
    logger.info("Index rebuild complete")


if __name__ == "__main__":
    asyncio.run(main())
