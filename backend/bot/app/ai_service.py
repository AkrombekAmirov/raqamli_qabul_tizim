"""Ollama AI integratsiyasi - oddiy savollarga avtomatik javob.

Qwen3:8b modeli orqali foydalanuvchilarning takrorlanuvchi va oddiy
savollariga javob beradi. Jiddiy masalalar (shikoyat, ariza, murakkab
holatlar) to'g'ridan-to'g'ri adminga yo'naltiriladi.
"""
import structlog
import httpx

from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()

SYSTEM_PROMPT = """Sen O'zbekiston davlat xizmatlari bo'yicha yordamchi botsan.
Sening vazifang foydalanuvchilarning oddiy va takrorlanuvchi savollariga javob berish.

Quyidagi turdagi savollarga javob bera olasan:
- Ish vaqti, manzil, bog'lanish ma'lumotlari
- Kerakli hujjatlar ro'yxati
- Umumiy yo'riqnomalar va qo'llanmalar
- Oddiy ma'lumot so'rovlari

QUYIDAGI HOLLARDA FAQAT "ADMIN_KERAK" deb javob ber:
- Shikoyat yoki norozilik bildirilsa
- Shaxsiy holat yoki murakkab masala bo'lsa
- Aniq javob bera olmasang
- Rasmiy qaror talab qilinsa
- Foydalanuvchi admin bilan gaplashmoqchi bo'lsa

Javoblaringni qisqa, aniq va o'zbek tilida ber.
Har doim hurmatli va professional bo'l.
"""


async def get_ai_response(user_message: str, category: str) -> tuple[str, bool]:
    """AI javob qaytaradi.
    
    Args:
        user_message: Foydalanuvchi xabari
        category: Murojaat kategoriyasi (complaint, suggestion, request, question)
    
    Returns:
        tuple[str, bool]: (javob_matni, admin_kerakmi)
        - Agar admin kerak bo'lsa: ("", True)
        - Agar AI javob bersa: (javob_matni, False)
    """
    # AI o'chirilgan bo'lsa
    if not settings.ai_enabled:
        return "", True
    
    # Shikoyat va arizalar DOIM adminga yo'naltiriladi
    if category in ("complaint", "request"):
        log.info("ai_skip_serious_category", category=category)
        return "", True
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": f"{SYSTEM_PROMPT}\n\nFoydalanuvchi savoli: {user_message}",
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 500,  # Javob uzunligi chegarasi
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            answer = result.get("response", "").strip()
            
            log.info("ai_response_received", answer_length=len(answer))
            
            # AI admin kerak deb qaror qildi
            if "ADMIN_KERAK" in answer.upper():
                log.info("ai_decided_admin_needed")
                return "", True
            
            # Bo'sh javob
            if not answer or len(answer) < 10:
                log.warning("ai_empty_response")
                return "", True
            
            return answer, False
            
    except httpx.TimeoutException:
        log.warning("ai_timeout")
        return "", True
    except httpx.HTTPStatusError as e:
        log.error("ai_http_error", status_code=e.response.status_code)
        return "", True
    except Exception as e:
        log.exception("ai_unexpected_error", error=str(e))
        return "", True


async def check_ollama_health() -> bool:
    """Ollama serverining ishlayotganini tekshiradi."""
    if not settings.ai_enabled:
        return False
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = [m.get("name") for m in data.get("models", [])]
            
            if settings.ollama_model in models:
                log.info("ollama_health_ok", model=settings.ollama_model)
                return True
            else:
                log.warning("ollama_model_not_found", 
                           required=settings.ollama_model, 
                           available=models)
                return False
    except Exception as e:
        log.warning("ollama_health_check_failed", error=str(e))
        return False
