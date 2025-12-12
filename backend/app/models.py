from pydantic import BaseModel, Field
from typing import Literal

ModelChoice = Literal["gpt", "claude", "mistral", "grok"]

class ChatRequest(BaseModel):
    """
    Defines the JSON body expected in the POST /chat request.
    Example: {"query": "Who is the CEO?", "model_id": "mistral"}
    """
    query: str = Field(..., description="User's question about Twinings Ovaltine")
    model_id: ModelChoice = Field(..., description="The name of the model to use for generating the answer")

class ChatResponse(BaseModel):
    """
    Defines the JSON body returned to the frontend.
    Example: {"answer": "The CEO is...", "model_used": "mistral"}
    """
    answer: str
    model_used: str