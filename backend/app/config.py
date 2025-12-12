import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # GPT
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_KEY: str = os.getenv("AZURE_OPENAI_KEY", "")
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

    # Claude
    CLAUDE_ENDPOINT: str = os.getenv("CLAUDE_ENDPOINT", "")
    CLAUDE_KEY: str = os.getenv("CLAUDE_KEY", "")
    CLAUDE_DEPLOYMENT: str = os.getenv("CLAUDE_DEPLOYMENT", "")

    # Mistral
    MISTRAL_ENDPOINT: str = os.getenv("MISTRAL_ENDPOINT", "")
    MISTRAL_KEY: str = os.getenv("MISTRAL_KEY", "")
    MISTRAL_DEPLOYMENT: str = os.getenv("MISTRAL_DEPLOYMENT", "")

    # Grok
    GROK_ENDPOINT: str = os.getenv("GROK_ENDPOINT", "")
    GROK_KEY: str = os.getenv("GROK_KEY", "")
    GROK_DEPLOYMENT: str = os.getenv("GROK_DEPLOYMENT", "")

    # Embedding
    EMBEDDING_ENDPOINT: str = os.getenv("EMBEDDING_ENDPOINT", "")
    EMBEDDING_KEY: str = os.getenv("EMBEDDING_KEY", "")
    EMBEDDING_DEPLOYMENT: str = os.getenv("EMBEDDING_DEPLOYMENT", "")

settings = Settings()