import requests
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun
from pydantic import PrivateAttr

# SDK Imports
from azure.ai.inference import ChatCompletionsClient, EmbeddingsClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from openai import AzureOpenAI, OpenAI

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

from app.config import settings


# --- 1. Chat Model Wrapper ---
class AzureMaaSChatModel(BaseChatModel):
    provider: str
    endpoint: str
    api_key: str
    deployment_name: str

    _client: Any = PrivateAttr(default=None)

    def __init__(self, provider: str, endpoint: str, api_key: str, deployment_name: str, **kwargs):
        super().__init__(
            provider=provider,
            endpoint=endpoint,
            api_key=api_key,
            deployment_name=deployment_name,
            **kwargs
        )
        self._initialize_client()

    def _initialize_client(self):
        if self.provider == "gpt":
            base_endpoint = self.endpoint
            if "/openai" in base_endpoint:
                base_endpoint = base_endpoint.split("/openai")[0]

            self._client = AzureOpenAI(
                azure_endpoint=base_endpoint,
                api_key=self.api_key,
                api_version="2024-12-01-preview"
            )

        elif self.provider == "mistral":
            self._client = ChatCompletionsClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key),
            )
        elif self.provider == "grok":
            self._client = OpenAI(base_url=self.endpoint, api_key=self.api_key)
        elif self.provider == "claude":
            if Anthropic:
                self._client = Anthropic(api_key=self.api_key, base_url=self.endpoint)
            else:
                raise ImportError("Anthropic SDK not installed.")

    def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any
    ) -> ChatResult:
        formatted_messages = []
        for msg in messages:
            role = "user"
            if isinstance(msg, SystemMessage):
                role = "system"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            formatted_messages.append({"role": role, "content": msg.content})

        content = ""
        try:
            if self.provider == "gpt":
                response = self._client.chat.completions.create(
                    model=self.deployment_name,
                    messages=formatted_messages,
                    # temperature=kwargs.get("temperature", 0.7),
                    max_completion_tokens=kwargs.get("max_tokens", 1024)  # Renamed from max_tokens
                )
                content = response.choices[0].message.content

            elif self.provider == "mistral":
                response = self._client.complete(
                    messages=formatted_messages,
                    model=self.deployment_name,
                    temperature=kwargs.get("temperature", 0.3)
                )
                content = response.choices[0].message.content

            elif self.provider == "grok":
                response = self._client.chat.completions.create(
                    model=self.deployment_name,
                    messages=formatted_messages,
                    temperature=kwargs.get("temperature", 0.3)
                )
                content = response.choices[0].message.content

            elif self.provider == "claude":
                system_msg = next((m['content'] for m in formatted_messages if m['role'] == 'system'), "")
                user_msgs = [m for m in formatted_messages if m['role'] != 'system']
                response = self._client.messages.create(
                    model=self.deployment_name,
                    messages=user_msgs,
                    system=system_msg,
                    max_tokens=1024,
                    temperature=kwargs.get("temperature", 0.3)
                )
                content = response.content[0].text

        except Exception as e:
            import traceback
            traceback.print_exc()
            content = f"Error generating response: {str(e)}"

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    @property
    def _llm_type(self) -> str:
        return f"azure-maas-{self.provider}"


class AzureMaaSEmbeddings(Embeddings):
    def __init__(self, endpoint, key, model_name):
        self.client = EmbeddingsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
        self.base_endpoint = endpoint.rstrip('/')
        # if self.base_endpoint.endswith("/v1"): self.base_endpoint = self.base_endpoint[:-3]
        # if self.base_endpoint.endswith("/openai"): self.base_endpoint = self.base_endpoint[:-7]
        self.key = key
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            response = self.client.embed(input=texts, model=self.model_name)
            return [item.embedding for item in response.data]
        except HttpResponseError:
            url = self.base_endpoint
            headers = {
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json"
            }
            payload = {
                "input": texts,
                "model": self.model_name,
                "encoding_format": "float"
            }
            r = requests.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            if "data" in data:
                return [item["embedding"] for item in data["data"]]
            if "embeddings" in data:
                return data["embeddings"]
            raise ValueError("Unknown embedding format")

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


def get_llm(model_id: str):
    if model_id == "gpt":
        return AzureMaaSChatModel("gpt", settings.AZURE_OPENAI_ENDPOINT, settings.AZURE_OPENAI_KEY,
                                  settings.AZURE_OPENAI_DEPLOYMENT)
    elif model_id == "claude":
        return AzureMaaSChatModel("claude", settings.CLAUDE_ENDPOINT, settings.CLAUDE_KEY, settings.CLAUDE_DEPLOYMENT)
    elif model_id == "mistral":
        return AzureMaaSChatModel("mistral", settings.MISTRAL_ENDPOINT, settings.MISTRAL_KEY,
                                  settings.MISTRAL_DEPLOYMENT)
    elif model_id == "grok":
        return AzureMaaSChatModel("grok", settings.GROK_ENDPOINT, settings.GROK_KEY, settings.GROK_DEPLOYMENT)
    else:
        raise ValueError(f"Unknown model ID: {model_id}")


def get_embeddings():
    return AzureMaaSEmbeddings(
        endpoint=settings.EMBEDDING_ENDPOINT,
        key=settings.EMBEDDING_KEY,
        model_name=settings.EMBEDDING_DEPLOYMENT
    )