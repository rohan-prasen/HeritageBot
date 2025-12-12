from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.rag_engine import generate_response

router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    model_id: str # gpt, claude, mistral, grok

class ChatResponse(BaseModel):
    answer: str
    model_used: str

@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    try:
        answer = await generate_response(payload.query, payload.model_id)
        return ChatResponse(answer=answer, model_used=payload.model_id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))