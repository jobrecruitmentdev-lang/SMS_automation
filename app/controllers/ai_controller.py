from fastapi import APIRouter
from app.models.ai import AiEnhanceRequest, AiEnhanceResponse
from app.services.ai_service import ai_service
from app.core.config import settings

router = APIRouter(tags=["AI Multi-LLM Engine"])

@router.post("/api/ai_enhance", response_model=AiEnhanceResponse)
def ai_enhance(req: AiEnhanceRequest):
    ok, text, prov = ai_service.enhance_template(
        req.template,
        tone=req.tone or "professional",
        job_title=req.job_title or "",
        company=req.company or "",
        provider=req.provider or "groq"
    )
    return AiEnhanceResponse(
        ok=ok,
        enhanced_text=text,
        character_count=len(text) if text else 0,
        provider_used=prov
    )

@router.get("/api/ai_models")
def get_ai_models():
    models = []
    if settings.GROQ_API_KEY:
        models.append({"id": "groq", "name": "Groq LLaMA-3.3 70B (Fastest)", "provider": "Groq", "active": True})
    if settings.GEMINI_API_KEY:
        models.append({"id": "gemini", "name": "Google Gemini 1.5 Flash", "provider": "Google", "active": True})
    if settings.NVIDIA_API_KEY:
        models.append({"id": "nvidia", "name": "NVIDIA Llama 3 70B", "provider": "NVIDIA", "active": True})
    if not models:
        models.append({"id": "offline", "name": "Built-in Rule Engine (Offline)", "provider": "Local", "active": True})
    return {"ok": True, "models": models}
