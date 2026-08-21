import re
import random
import requests
from app.core.config import settings
from app.core.state import write_log

# GSM 7-bit standard alphabet
GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ"
    " !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENDED = "|^€{}[~]\\\x0c"

def is_gsm7_character(char: str) -> bool:
    return char in GSM7_BASIC or char in GSM7_EXTENDED

def calculate_sms_encoding(text: str) -> dict:
    if not text:
        return {
            "encoding": "GSM-7",
            "length": 0,
            "segments": 1,
            "char_limit_single": 160,
            "char_limit_multi": 153,
            "chars_remaining_in_segment": 160,
            "is_unicode": False
        }
    
    is_unicode = any(not is_gsm7_character(c) for c in text)
    if is_unicode:
        length = len(text)
        single_limit = 70
        multi_limit = 67
        encoding_name = "UCS-2 (Unicode)"
    else:
        length = sum(2 if c in GSM7_EXTENDED else 1 for c in text)
        single_limit = 160
        multi_limit = 153
        encoding_name = "GSM-7 (Standard)"
    
    if length <= single_limit:
        segments = 1
        chars_remaining = single_limit - length
    else:
        segments = (length + multi_limit - 1) // multi_limit
        chars_remaining = (segments * multi_limit) - length

    return {
        "encoding": encoding_name,
        "length": length,
        "segments": segments,
        "char_limit_single": single_limit,
        "char_limit_multi": multi_limit,
        "chars_remaining_in_segment": chars_remaining,
        "chars_left": chars_remaining,
        "is_unicode": is_unicode
    }

def evaluate_spintax(template: str, seed: int = 0) -> str:
    if not template:
        return ""
    if seed:
        random.seed(seed)
    pattern = re.compile(r'\{([^{}]+)\}')
    current = template
    max_loops = 10
    while max_loops > 0:
        match = pattern.search(current)
        if not match:
            break
        choices = match.group(1).split('|')
        picked = random.choice(choices)
        current = current[:match.start()] + picked + current[match.end():]
        max_loops -= 1
    return current

class AiOrchestrator:
    def __init__(self):
        self.groq_key = settings.GROQ_API_KEY
        self.gemini_key = settings.GEMINI_API_KEY
        self.nvidia_key = settings.NVIDIA_API_KEY

    def enhance_template(self, template: str, tone: str = "professional", job_title: str = "", company: str = "", provider: str = "groq"):
        system_prompt = (
            "You are a world-class Indian HR & Talent Acquisition SMS Copywriter. "
            "Your task is to take a job outreach template and re-write it to be concise, engaging, and professional. "
            "Keep the output strictly under 160 characters (1 single GSM-7 SMS segment). "
            "Use place-holders like {candidate_name}, {job_title}, {company_name} if present. "
            "Return ONLY the rewritten SMS text without quotation marks or explanations."
        )
        user_prompt = f"Tone: {tone}\nJob Title: {job_title or 'Open Position'}\nCompany: {company or 'JobRecruitment'}\nTemplate: {template}"

        # 1. Try Groq (Llama 3.3 70B / 8B)
        if provider == "groq" and self.groq_key:
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                        "temperature": 0.7,
                        "max_tokens": 120
                    },
                    timeout=10
                )
                if r.status_code == 200:
                    text = r.json()["choices"][0]["message"]["content"].strip().strip('"')
                    return True, text, "Groq (Llama 3.3 70B)"
            except Exception as e:
                write_log(f"Groq API error: {e}")

        # 2. Try Gemini
        if self.gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
                r = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}]},
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"')
                    return True, text, "Google Gemini 1.5 Flash"
            except Exception as e:
                write_log(f"Gemini API error: {e}")

        # 3. Fallback: Clean formatted local template
        fallback = f"Hi {{candidate_name}}, JobRecruitment has an opening for {job_title or 'a role'}. Review details & apply: jobrecruitment.in"
        return True, fallback, "Built-in Rule Engine (Offline)"

ai_service = AiOrchestrator()
