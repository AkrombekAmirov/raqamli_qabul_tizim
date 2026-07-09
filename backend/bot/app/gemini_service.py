"""Gemini Pro API integratsiyasi - qat'iy qoidalar bilan avtomatik javob.

google-generativeai orqali ishlaydi. Faqat bazadagi ma'lumotlarga
asoslanib javob beradi. Jiddiy masalalar darhol adminga yo'naltiriladi.
"""
import structlog
import google.generativeai as genai
import os
import asyncio

from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()

if settings.gemini_api_key and settings.ai_enabled:
    genai.configure(api_key=settings.gemini_api_key)

# Hujjatlar bazasini o'qish
KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), "docs", "knowledge_base.txt")
try:
    with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
        KNOWLEDGE_BASE_TEXT = f.read()
except FileNotFoundError:
    KNOWLEDGE_BASE_TEXT = "Hujjatlar bazasi hali shakllantirilmagan."

SYSTEM_PROMPT = f"""Sen O'zbekiston Respublikasi kelajak markazining rasmiy botisan.
Sening vazifang quyidagi ICHKI HUJJATLAR BAZASI asosida foydalanuvchilarning savollariga aniq, to'g'ri va qisqa javob berishdir.

--- ICHKI HUJJATLAR BAZASI BOSHLANISHI ---
{KNOWLEDGE_BASE_TEXT}
--- ICHKI HUJJATLAR BAZASI TUGASHI ---

QAT'IY QOIDALAR (BUZISH QAT'IYAN MAN ETILADI):
1. JAVOB BERISH: Faqatgina yuqoridagi 'ICHKI HUJJATLAR BAZASI'da mavjud bo'lgan ma'lumotlarga asoslanib javob ber. O'zingdan birorta ham so'z, raqam yoki ma'lumot to'qib chiqarma.
2. ADMIN_KERAK SIGNALINI BERISH: Agar foydalanuvchi so'ragan ma'lumot 'ICHKI HUJJATLAR BAZASI'da aniq ko'rsatilmagan bo'lsa, YOKI foydalanuvchi quyidagi mavzularda yozyotgan bo'lsa darhol va faqatgina 'ADMIN_KERAK' deb javob qaytar:
   - Shikoyat yoki norozilik (ayniqsa xodimlar ustidan shikoyat)
   - Poraxo'rlik yoki korrupsiya
   - Shaxsiy huquqiy holat yoki jiddiy muammo
   - Admin/rahbar bilan ulanish talabi
   - Har qanday noaniq holat
3. FORMAT: Javoblaring hurmat bilan, professional va sof o'zbek tilida bo'lishi shart. Agar sen bilmaydigan yoki hujjatsiz holat bo'lsa hech narsani tushuntirib o'tirma, shunchaki ADMIN_KERAK deb yoz!
"""

async def get_ai_response(user_message: str, category: str = "question") -> tuple[str, bool]:
    """Gemini AI orqali javob qaytaradi.
    
    Args:
        user_message: Foydalanuvchi xabari
        category: Murojaat kategoriyasi (faqat question yoki suggestion bo'lsa keladi)
        
    Returns:
        tuple[str, bool]: (javob_matni, admin_kerakmi)
    """
    if not settings.ai_enabled or not settings.gemini_api_key:
        return "", True
    
    # Shikoyat va arizalar asosan handlers ichida bloklanadi, ammo xavfsizlik uchun tekshirib qo'yamiz
    if category in ("complaint", "request"):
        log.info("gemini_skip_serious_category", category=category)
        return "", True
        
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        # Async chaqiruvni bloklanmaydigan qilib yozamiz
        prompt = f"{SYSTEM_PROMPT}\n\nFoydalanuvchi so'rovi:\n{user_message}"
        
        # loop.run_in_executor yordamida sinxron funksiyani async da ishlatamiz
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0, # 0.0 qilinadi, chunki faktlardan og'ishmasligi kerak
                    top_p=0.9,
                )
            )
        )
        
        answer = response.text.strip()
        log.info("gemini_response_received", answer_length=len(answer))
        
        if "ADMIN_KERAK" in answer.upper():
            log.info("gemini_decided_admin_needed")
            return "", True
            
        if not answer or len(answer) < 5:
            return "", True
            
        return answer, False
        
    except Exception as e:
        log.exception("gemini_error", error=str(e))
        return "", True
