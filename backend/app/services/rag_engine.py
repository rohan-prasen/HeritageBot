import os
import logging
import json
import asyncio
from langchain_community.vectorstores import FAISS
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from app.services.azure_client_factory import get_llm, get_embeddings

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("langchain_core.vectorstores.base").setLevel(logging.ERROR)

# --- 1. Resources Setup ---

# OPTIMIZATION: Reduce max_results to 3 to speed up the scraper
search_wrapper = DuckDuckGoSearchAPIWrapper(region="uk-en", max_results=3)
web_search_tool = DuckDuckGoSearchRun(api_wrapper=search_wrapper)

embeddings = get_embeddings()
DB_FOLDER = "faiss_index"
DB_NAME = "twinings_index"


def get_local_retriever():
    if os.path.exists(DB_FOLDER):
        try:
            vectorstore = FAISS.load_local(
                DB_FOLDER,
                embeddings,
                index_name=DB_NAME,
                allow_dangerous_deserialization=True
            )
            # High threshold to drop garbage matches
            return vectorstore.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"score_threshold": 0.6, "k": 2}
            )
        except Exception:
            return None
    return None


# --- 2. Combined Supervisor (Speed Boost) ---

async def plan_search_and_validate(query: str, model_id: str):
    """
    Combines Guardrail Check AND Search Planning into ONE LLM call
    to reduce latency.
    """
    llm = get_llm(model_id)

    supervisor_prompt = ChatPromptTemplate.from_template(
        """You are the Supervisor for the 'Twinings Ovaltine' Intelligence Unit.

        User Query: "{query}"

        **Task 1: Relevance Check**
        Is this query related to:
        - Twinings or Ovaltine brands?
        - Their parent companies (Associated British Foods / ABF, Wander AG)?
        - Their executives, history, legal issues, or business operations?

        **Task 2: Execution Plan**
        If YES: Generate 2 specific search queries to find the answer. Include "Twinings Ovaltine" or "ABF" in the queries to ensure precision.
        If NO: Return relevant=false.

        **Output Format (JSON ONLY):**
        {{
            "relevant": true,
            "queries": ["query 1", "query 2"]
        }}
        OR
        {{
            "relevant": false,
            "reason": "Off-topic"
        }}
        """
    )

    chain = supervisor_prompt | llm | StrOutputParser()
    try:
        result = await chain.ainvoke({"query": query})
        cleaned = result.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Supervisor Error: {e}")
        # Fail-safe: assume relevant if LLM breaks, generic query
        return {"relevant": True, "queries": [f"Twinings Ovaltine {query}"]}


# --- 3. Strict Content Filtering (Output Guardrail) ---

def filter_irrelevant_content(results: list[str]) -> str:
    """
    Hard Guardrail: Discards search results that don't explicitly mention
    our target entities. This prevents "generic tea info" pollution.
    """
    # Expanded list of valid entities
    valid_keywords = [
        "twining", "ovaltine", "abf", "associated british foods",
        "wander ag", "r. twining", "stephen twining"
    ]

    filtered_text = []
    seen = set()

    for res in results:
        # 1. Dedup
        h = hash(res[:50])
        if h in seen: continue
        seen.add(h)

        # 2. Keyword Check
        if any(k in res.lower() for k in valid_keywords):
            filtered_text.append(res)
        else:
            logger.info(f"Dropped irrelevant snippet: {res[:50]}...")

    return "\n\n".join(filtered_text)


# --- 4. Deep Context Fetcher ---

async def execute_search(query: str):
    """Async wrapper for the sync tool"""
    try:
        # Add timeout to prevent hanging
        return await asyncio.to_thread(web_search_tool.invoke, query)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return ""


async def fetch_validated_context(plan, query):
    if not plan.get("relevant", False):
        return None

    # Parallel Search
    search_queries = plan.get("queries", [])[:2]  # Limit to 2 for speed
    logger.info(f"Executing Searches: {search_queries}")

    tasks = [execute_search(q) for q in search_queries]
    raw_results = await asyncio.gather(*tasks)

    # Filter Results
    clean_web_context = filter_irrelevant_content(raw_results)

    # Local DB (Optional)
    local_context = ""
    retriever = get_local_retriever()
    if retriever:
        try:
            docs = await retriever.ainvoke(query)
            if docs:
                local_context = "\n".join([doc.page_content for doc in docs])
        except Exception:
            pass

    # Final Assembly
    full_context = ""
    if clean_web_context:
        full_context += f"--- WEB DATA ---\n{clean_web_context}\n"
    if local_context:
        full_context += f"--- INTERNAL DATA ---\n{local_context}\n"

    return full_context.strip()


# --- 5. Main Generation ---

FINAL_PROMPT = """
You are a Strategy Analyst for 'Twinings Ovaltine'.

**Context:**
{context}

**Instructions:**
1. Answer the question based **ONLY** on the provided Context.
2. If the Context is empty, return exactly: "Data not found regarding this query."
3. Be concise and professional.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", FINAL_PROMPT),
    ("user", "{question}")
])


async def generate_response(query: str, model_id: str):
    # 1. Plan (Fast Check)
    plan = await plan_search_and_validate(query, model_id)

    if not plan.get("relevant"):
        return "Beyond my scope."

    # 2. Fetch & Filter (Heavy Lifting)
    context_data = await fetch_validated_context(plan, query)

    # 3. Fail Fast (Output Guardrail)
    if not context_data:
        return "Data not found regarding this query."

    # 4. Generate Answer
    llm = get_llm(model_id)
    chain = prompt | llm | StrOutputParser()

    return await chain.ainvoke({
        "context": context_data,
        "question": query
    })