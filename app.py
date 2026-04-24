import os
import time
import threading
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HTTP = requests.Session()
HTTP.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ar-DZ,ar;q=0.9,en-US;q=0.7,en;q=0.6",
})

_retry = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=0.7,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST", "GET"]
)

_adapter = HTTPAdapter(max_retries=_retry, pool_connections=50, pool_maxsize=50)
HTTP.mount("https://", _adapter)
HTTP.mount("http://", _adapter)

import datetime
import base64
import json
import re
import random
import io
try:
    from PIL import Image, ImageOps, ImageEnhance
except Exception:
    Image = None
    ImageOps = None
    ImageEnhance = None

try:
    import pytesseract
except Exception:
    pytesseract = None
from flask import Flask, request, jsonify

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "faresdz123")

CLAUDE45_URL = os.getenv("CLAUDE45_URL", "http://apo-fares.abrdns.com/Claude-Sonnet-4.5.php").strip()

# ✅ Nano Banana (Text-to-Image + Edit) ✅✅✅
NANO_BANANA_URL = os.getenv("NANO_BANANA_URL", "https://zecora0.serv00.net/ai/NanoBanana.php")


# ✅ OCR (fallback)
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "").strip()

user_memory = {}
user_state = {}
pending_images = {}

# ---------------------------
# ✅ LOGS Helper
# ---------------------------
def _log(tag: str, msg: str):
    try:
        print(f"[{tag}] {msg}")
    except:
        pass

def _short(s: str, n: int = 700):
    s = s or ""
    return s[:n]
    
def _clip(s: str, n: int = 900) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[:n].strip()

# ✅ حطهم هنا
def mem_get(uid):
    return user_memory.get(uid, [])

def mem_push(uid, role, content, max_keep=25):
    arr = user_memory.get(uid) or []
    arr.append({"role": role, "content": _clip(content, 500)})
    if len(arr) > max_keep:
        arr = arr[-max_keep:]
    user_memory[uid] = arr
def _sleep_backoff(attempt: int, retry_after: str = None):
    try:
        if retry_after:
            sec = float(retry_after)
            if sec > 0:
                time.sleep(min(sec, 20))
                return
    except:
        pass
    time.sleep(min(1.0 * (2 ** attempt), 12))
    


def _messages_to_prompt(messages):
    lines = []
    for m in (messages or []):
        role = (m.get("role") or "").lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            lines.append(f"[SYSTEM]\n{content}\n")
        elif role == "user":
            lines.append(f"[USER]\n{content}\n")
        else:
            lines.append(f"[ASSISTANT]\n{content}\n")
    lines.append("[ASSISTANT]\n")
    return "\n".join(lines)
    
def safe_text(text, limit=1200):
    text = (text or "").strip()

    # تنظيف المسافات
    text = re.sub(r"\s+", " ", text)

    # تقطيع ذكي
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0]

    return text

def claude45_answer(messages, user_id=None, timeout=30):
    if not messages:
        return ""

    url = "https://viscodev.x10.mx/ClaudeM/api.php"

    # استخراج system
    system = ""
    if messages and messages[0].get("role") == "system":
        system = messages[0]["content"]

    system = safe_text(system, 700)

    # تحويل باقي الرسائل
    user_prompt = _messages_to_prompt(messages[1:])
    user_prompt = safe_text(user_prompt, 1200)

    # دمج نهائي
    full_prompt = safe_text(system + "\n\n" + user_prompt, 1500)

    try:
        r = HTTP.get(
            url,
            params={"text": full_prompt},  # 🔥 مضمون ما يتعداش limit
            timeout=timeout
        )

        print("STATUS:", r.status_code)
        print("RAW:", r.text[:300])

        r.raise_for_status()

        try:
            js = r.json()
            answer = (
                js.get("response")
                or js.get("answer")
                or js.get("text")
                or js.get("message")
                or ""
            )
        except:
            answer = r.text or ""

        return clean_reply(answer.strip())

    except Exception as e:
        print("CLAUDE ERROR:", repr(e))
        return ""
# ---------------------------
# ✅ 58 ولاية
# ---------------------------
WILAYAS = [
    ("أدرار","Adrar","Adrar"),
    ("الشلف","Chlef","Chlef"),
    ("الأغواط","Laghouat","Laghouat"),
    ("أم البواقي","Oum El Bouaghi","Oum El Bouaghi"),
    ("باتنة","Batna","Batna"),
    ("بجاية","Bejaia","Bejaia"),
    ("بسكرة","Biskra","Biskra"),
    ("بشار","Bechar","Bechar"),
    ("البليدة","Blida","Blida"),
    ("البويرة","Bouira","Bouira"),
    ("تمنراست","Tamanrasset","Tamanrasset"),
    ("تبسة","Tebessa","Tebessa"),
    ("تلمسان","Tlemcen","Tlemcen"),
    ("تيارت","Tiaret","Tiaret"),
    ("تيزي وزو","Tizi Ouzou","Tizi Ouzou"),
    ("الجزائر","Algiers","Algiers"),
    ("الجلفة","Djelfa","Djelfa"),
    ("جيجل","Jijel","Jijel"),
    ("سطيف","Setif","Setif"),
    ("سعيدة","Saida","Saida"),
    ("سكيكدة","Skikda","Skikda"),
    ("سيدي بلعباس","Sidi Bel Abbes","Sidi Bel Abbes"),
    ("عنابة","Annaba","Annaba"),
    ("قالمة","Guelma","Guelma"),
    ("قسنطينة","Constantine","Constantine"),
    ("المدية","Medea","Medea"),
    ("مستغانم","Mostaganem","Mostaganem"),
    ("المسيلة","M'Sila","M'Sila"),
    ("معسكر","Mascara","Mascara"),
    ("ورقلة","Ouargla","Ouargla"),
    ("وهران","Oran","Oran"),
    ("البيض","El Bayadh","El Bayadh"),
    ("إليزي","Illizi","Illizi"),
    ("برج بوعريريج","Bordj Bou Arreridj","Bordj Bou Arreridj"),
    ("بومرداس","Boumerdes","Boumerdes"),
    ("الطارف","El Tarf","El Tarf"),
    ("تندوف","Tindouf","Tindouf"),
    ("تيسمسيلت","Tissemsilt","Tissemsilt"),
    ("الوادي","El Oued","El Oued"),
    ("خنشلة","Khenchela","Khenchela"),
    ("سوق أهراس","Souk Ahras","Souk Ahras"),
    ("تيبازة","Tipaza","Tipaza"),
    ("ميلة","Mila","Mila"),
    ("عين الدفلى","Ain Defla","Ain Defla"),
    ("النعامة","Naama","Naama"),
    ("عين تموشنت","Ain Temouchent","Ain Temouchent"),
    ("غرداية","Ghardaia","Ghardaia"),
    ("غليزان","Relizane","Relizane"),
    ("تيميمون","Timimoun","Timimoun"),
    ("برج باجي مختار","Bordj Badji Mokhtar","Bordj Badji Mokhtar"),
    ("أولاد جلال","Ouled Djellal","Ouled Djellal"),
    ("بني عباس","Beni Abbes","Beni Abbes"),
    ("إن صالح","In Salah","In Salah"),
    ("إن قزام","In Guezzam","In Guezzam"),
    ("تقرت","Touggourt","Touggourt"),
    ("جانت","Djanet","Djanet"),
    ("المغير","El M'Ghair","El M'Ghair"),
    ("المنيعة","El Meniaa","El Meniaa"),
]
W_BY_AR = {a: {"ar": a, "en": e, "city": c} for a, e, c in WILAYAS}
W_BY_EN = {e.lower(): {"ar": a, "en": e, "city": c} for a, e, c in WILAYAS}

def normalize_name(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("ولاية", "").strip()
    return s

def resolve_wilaya(user_text: str):
    name = normalize_name(user_text)
    if not name:
        return None
    if name in W_BY_AR:
        return W_BY_AR[name]
    low = name.lower()
    if low in W_BY_EN:
        return W_BY_EN[low]
    if low in ["alger", "alg", "algiers city"]:
        return W_BY_EN.get("algiers")
    if low in ["oran city"]:
        return W_BY_EN.get("oran")
    return None

# ---------------------------
# صفحات ضرورية لفيسبوك
# ---------------------------
@app.route("/test", methods=["GET"])
def test():
    return "السيرفر راه يخدم", 200

@app.route("/privacy", methods=["GET"])
def privacy():
    return """
    <h1>Privacy Policy</h1>
    <p>This bot replies to messages on Facebook Messenger.</p>
    <p>We do not sell personal data.</p>
    <p>We keep only temporary conversation context to reply, then it gets overwritten.</p>
    """, 200

@app.route("/delete-data", methods=["GET"])
def delete_data():
    return """
    <h1>Data Deletion Instructions</h1>
    <p>If you want your data deleted, send us a message on our Facebook page requesting deletion.</p>
    <p>We will remove all conversation data immediately.</p>
    """, 200

# ---------------------------
# أدوات Messenger
# ---------------------------
def fb_post(url, payload, timeout=20):
    if not PAGE_ACCESS_TOKEN:
        return None, "PAGE_ACCESS_TOKEN ناقص"
    full = f"https://graph.facebook.com/v18.0{url}"
    try:
        r = requests.post(full, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=timeout)
        return r, None
    except Exception as e:
        return None, repr(e)

def send_typing(recipient_id, action="typing_on"):
    payload = {"recipient": {"id": recipient_id}, "sender_action": action}
    fb_post("/me/messages", payload, timeout=10)

def send_message(recipient_id, text):
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    fb_post("/me/messages", payload, timeout=20)

def send_quick_replies(recipient_id, text, replies):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "quick_replies": [
                {"content_type": "text", "title": r["title"][:20], "payload": r["payload"]}
                for r in replies
            ]
        }
    }
    fb_post("/me/messages", payload, timeout=20)

def chunk_text(text: str, max_len: int = 1500):
    t = (text or "").strip()
    if not t:
        return []

    parts = []
    while len(t) > max_len:
        cut = t.rfind(".", 0, max_len)
        if cut < 500:
            cut = max_len
        parts.append(t[:cut + 1].strip())
        t = t[cut + 1:].strip()

    if t:
        parts.append(t)

    return parts

def send_long_message(recipient_id, text):
    parts = chunk_text(text, max_len=1500)
    for p in parts:
        send_message(recipient_id, p)
        time.sleep(0.05)  # أسرع من 0.2

def fb_upload_image_bytes(image_bytes: bytes, timeout=60) -> str:
    if not PAGE_ACCESS_TOKEN:
        raise Exception("PAGE_ACCESS_TOKEN ناقص")

    url = "https://graph.facebook.com/v18.0/me/message_attachments"
    files = {"filedata": ("image.png", image_bytes, "image/png")}
    data = {
        "message": json.dumps({
            "attachment": {"type": "image", "payload": {"is_reusable": True}}
        })
    }

    r = requests.post(url, params={"access_token": PAGE_ACCESS_TOKEN}, files=files, data=data, timeout=timeout)
    if not r.ok:
        raise Exception(f"fb_upload_error {r.status_code} {(r.text or '')[:200]}")
    return (r.json() or {}).get("attachment_id")

def send_image_attachment_id(recipient_id, attachment_id, caption=None):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"attachment_id": attachment_id}
            }
        }
    }
    fb_post("/me/messages", payload, timeout=30)
    if caption:
        send_message(recipient_id, caption)

# ---------------------------
# ✅ Setup (Get Started + Ice Breakers + Persistent Menu)
# ---------------------------
def setup_messenger_profile():
    profile_payload = {
        "get_started": {"payload": "GET_STARTED"},
        "ice_breakers": [
            {"question": "🌦️ الطقس", "payload": "CMD_WEATHER"},
            {"question": "🕌 أوقات الصلاة", "payload": "CMD_PRAYER"},
            {"question": "🎨 توليد صورة", "payload": "CMD_IMAGE"},
            {"question": "🖼️ حل صورة/موضوع", "payload": "CMD_VISION"},
            {"question": "ℹ️ About Botivity", "payload": "CMD_ABOUT"},
        ],
        "persistent_menu": [
            {
                "locale": "default",
                "composer_input_disabled": False,
                "call_to_actions": [
                    {"type": "postback", "title": "🌦️ الطقس", "payload": "CMD_WEATHER"},
                    {"type": "postback", "title": "🕌 الصلاة", "payload": "CMD_PRAYER"},
                    {"type": "postback", "title": "🎨 صورة", "payload": "CMD_IMAGE"},
                    {"type": "postback", "title": "🖼️ حل صورة", "payload": "CMD_VISION"},
                    {"type": "postback", "title": "ℹ️ About", "payload": "CMD_ABOUT"},
                ]
            }
        ]
    }

    r, err = fb_post("/me/messenger_profile", profile_payload, timeout=25)
    if err:
        return {"ok": False, "error": err}
    return {"ok": r.ok, "status": r.status_code, "response": r.text}

@app.route("/setup", methods=["GET"])
def setup():
    result = setup_messenger_profile()
    print("SETUP RESULT:", result)
    return jsonify(result), (200 if result.get("ok") else 500)

# ---------------------------
# تنظيف الرد
# ---------------------------
def clean_reply(text: str) -> str:

    if not text:
        return "صرا مشكل فالسيرفر 😅 جرّب عاود بعد شوية."

    forbidden = [
        r"\bopenai\b",
        r"ذكاء\s*اصطناعي",
        r"نموذج\s*لغوي",
        r"language\s*model",
        r"\bllm\b",
        r"artificial\s*intelligence",
        r"developed\s*by",
        r"created\s*by",
        r"تم\s*تطويري",
        r"تم\s*إنشائي",
        r"i\s+am\s+an?\s+ai",
        r"i\s+am\s+a\s+language\s+model",
    ]

    cleaned = text

    for pattern in forbidden:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    if not cleaned or len(cleaned) < 2:
        return "صرا مشكل فالسيرفر 😅 جرّب عاود بعد شوية."

    return cleaned
# ---------------------------
    
def vision_via_ocr_and_fares(img_url: str, intent_text: str, user_msg: str = "", user_id: str = None) -> str:
    img_bytes = download_image_bytes(img_url)

    extracted = ocr_extract_text(img_bytes)
    if not extracted.strip():
        return "ما قدرتش نقرأ النص من الصورة 😅\nجرّب قرّب للصورة/زيد الإضاءة/بلا ظل."

    lang = detect_lang_pref(user_msg)

    if lang == "fr":
        rules = "Réponds en français: clair, structuré, pas trop long, avec quelques emojis 🙂."
    elif lang == "en":
        rules = "Reply in English: clear, structured, not too long, with a few emojis 🙂."
    elif lang == "ar_fusha":
        rules = "أجب بالعربية الفصحى: واضح ومنظم دون إطالة، مع بعض الإيموجي 🙂."
    else:
        rules = "جاوب بالدارجة الجزائرية: مرتب ومختصر ومع شوية ايموجيات 🙂."

    prompt = f"""
أنت Botivity (بوت مسنجر).
عندك نص مستخرج من صورة.

المطلوب:
{intent_text}

النص:
{extracted}

قواعد:
- {rules}
- عناوين قصيرة.
- في الآخر: 📌 الخلاصة.
- ممنوع ذكر أي أسماء نماذج/شركات.
""".strip()

    # ✅ messages (نقدر نزيد history اذا حبّيت)
    messages = [{"role": "system", "content": "جاوب كيما Botivity: منظم، سمح، واضح."}]
    if user_id:
        messages += mem_get(user_id)
    messages.append({"role": "user", "content": prompt})

    raw = claude45_answer(messages, timeout=60)
    ans = clean_reply(raw)

    if user_id and ans:
        mem_push(user_id, "user", "[VISION]")
        mem_push(user_id, "assistant", ans)

    return ans.strip() or "صرا مشكل فالإجابة 😅 جرّب عاود."
    
# ---------------------------
# ✅ Nano Banana - توليد/تعديل صورة
# ---------------------------
def _tight_prompt(user_prompt: str) -> str:
    p = (user_prompt or "").strip()
    if not p:
        return ""
    return (
        f"{p}\n"
        "Requirements: follow the description exactly, no extra objects, no random text, high quality, sharp details."
    )

def nano_banana_call(text: str, image_url: str = None) -> dict:
    if not NANO_BANANA_URL:
        raise Exception("NANO_BANANA_URL ناقص")

    params = {"text": text}
    if image_url:
        params["links"] = image_url

    _log("NANO", f"GET -> {NANO_BANANA_URL} text_len={len(text)} edit={bool(image_url)}")
    r = requests.get(NANO_BANANA_URL, params=params, timeout=180)
    _log("NANO", f"STATUS {r.status_code} CT={r.headers.get('content-type')}")
    _log("NANO", f"BODY {_short(r.text, 700)}")

    r.raise_for_status()
    try:
        return r.json() or {}
    except:
        return {}

def nano_banana_create_image_bytes(prompt: str) -> bytes:
    p = _tight_prompt(prompt)
    if not p:
        raise ValueError("empty prompt")

    js = nano_banana_call(p, image_url=None)

    if not js.get("success") or not js.get("url"):
        err = js.get("error") or "Unknown error"
        raise Exception(f"nano_banana_failed {err}")

    img_url = js["url"]
    _log("NANO", f"IMAGE URL: {img_url}")
    img = requests.get(img_url, timeout=120)
    _log("NANO", f"IMG STATUS {img.status_code} CT={img.headers.get('content-type')}")
    img.raise_for_status()
    return img.content

def nano_banana_edit_image_bytes(image_url: str, prompt: str) -> bytes:
    p = _tight_prompt(prompt)
    if not p:
        raise ValueError("empty prompt")
    if not image_url:
        raise ValueError("empty image_url")

    js = nano_banana_call(p, image_url=image_url)

    if not js.get("success") or not js.get("url"):
        err = js.get("error") or "Unknown error"
        raise Exception(f"nano_banana_edit_failed {err}")

    out_url = js["url"]
    _log("NANO", f"EDIT OUT URL: {out_url}")
    img = requests.get(out_url, timeout=120)
    _log("NANO", f"IMG STATUS {img.status_code} CT={img.headers.get('content-type')}")
    img.raise_for_status()
    return img.content

# ---------------------------
# ✅ Image downloader + data URL
# ---------------------------
def download_image_bytes(image_url: str) -> bytes:
    _log("IMG", f"GET {image_url}")
    r = requests.get(image_url, timeout=40)
    _log("IMG", f"STATUS {r.status_code} CT={r.headers.get('content-type')}")
    r.raise_for_status()
    return r.content

def guess_mime(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG"):
        return "image/png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return "application/octet-stream"

def to_data_url(image_bytes: bytes) -> str:
    mime = guess_mime(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

# ---------------------------
# ✅ Language detect (AR/DZ/FR/EN)
# ---------------------------
def detect_lang_pref(txt: str) -> str:
    t = (txt or "").lower()

    # طلب صريح
    if "بالفرنسية" in t or "français" in t or "francais" in t:
        return "fr"
    if "بالانجليزية" in t or "english" in t:
        return "en"
    if "بالفصحى" in t or "فصحى" in t:
        return "ar_fusha"

    # كشف سريع
    fr_hits = [" je ", " tu ", " vous", " pour", " avec", " merci", " s'il", " salut", " bonjour"]
    en_hits = [" what", " how", " please", " solve", " answer", " english", " thanks", " hi "]
    if any(x in t for x in fr_hits): return "fr"
    if any(x in t for x in en_hits): return "en"
    return "dz"


# ---------------------------
# ✅ OCR Preprocess (makes low-quality images readable)
# ---------------------------
def preprocess_for_ocr(image_bytes: bytes) -> bytes:
    if Image is None:
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    w, h = img.size
    if max(w, h) < 1200:
        img = img.resize((w * 2, h * 2))

    img = ImageOps.grayscale(img)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.point(lambda x: 255 if x > 150 else 0)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def ocr_tesseract(image_bytes: bytes) -> str:
    if (Image is None) or (pytesseract is None):
        return ""
    pre = preprocess_for_ocr(image_bytes)
    img = Image.open(io.BytesIO(pre))
    txt = pytesseract.image_to_string(img, lang="ara+eng+fra")
    return (txt or "").strip()


# ---------------------------
# ✅ Make answers shorter + nicer
# ---------------------------
def _shorten_reply(text: str, max_chars: int = 1800) -> str:
    t = (text or "").strip()
    if not t:
        return t
    if len(t) <= max_chars:
        return t

    # try cut at a safe boundary
    cut = t.rfind("\n", 0, max_chars)
    if cut < 800:
        cut = max_chars
    return (t[:cut].strip() + "\n\n…")
    
# ---------------------------
# ✅ OCR (fallback)
# ---------------------------

def ocr_extract_text(image_bytes: bytes) -> str:
    # ✅ حضّر الصورة (ينفع لـ tesseract و OCR.Space)
    pre = preprocess_for_ocr(image_bytes)

    # 1) ✅ OCR محلي (إذا متوفر)
    try:
        t = ocr_tesseract(image_bytes)
        if t and len(t) > 10:
            _log("OCR", f"TESS OK len={len(t)}")
            return t
    except Exception as e:
        _log("OCR", f"TESS FAIL {repr(e)}")

    # 2) ✅ fallback OCR.Space
    if not OCR_SPACE_API_KEY:
        _log("OCR", "OCR_SPACE_API_KEY empty + tesseract failed")
        return ""

    url = "https://api.ocr.space/parse/image"

    mime = guess_mime(pre)
    filename = "image.png" if mime == "image/png" else "image.jpg"
    files = {"file": (filename, pre, mime)}
    headers = {"apikey": OCR_SPACE_API_KEY}

    def _do(lang: str) -> str:
        data = {
            "language": lang,
            "isOverlayRequired": "false",
            "detectOrientation": "true",
            "scale": "true",
            "OCREngine": "2",
        }
        _log("OCR", f"OCR.Space lang={lang}")
        res = requests.post(url, files=files, data=data, headers=headers, timeout=90)
        _log("OCR", f"STATUS={res.status_code}")
        _log("OCR", f"BODY={_short(res.text, 600)}")
        if not res.ok:
            return ""
        js = res.json() or {}
        if js.get("IsErroredOnProcessing"):
            return ""
        parsed = js.get("ParsedResults") or []
        if not parsed:
            return ""
        return (parsed[0].get("ParsedText") or "").strip()

    # ✅ جرّب لغات بالتوالي (مش غير E201)
    t = _do("ara")
    if not t:
        t = _do("eng")
    if not t:
        t = _do("fre")
    return t or ""
# ---------------------------
# ✅ Weather + Prayer
# ---------------------------
AR_DAYS = ["الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
AR_WIND_DIR = [
    "شمال ⬆️", "شمال-شرق ↗️", "شرق ➡️", "جنوب-شرق ↘️",
    "جنوب ⬇️", "جنوب-غرب ↙️", "غرب ⬅️", "شمال-غرب ↖️"
]

def wind_dir(deg):
    try:
        deg = float(deg)
        ix = int((deg + 22.5) // 45) % 8
        return AR_WIND_DIR[ix]
    except:
        return "—"

def fmt_num(x, suffix=""):
    try:
        if x is None:
            return "—"
        if isinstance(x, (int, float)):
            if float(x).is_integer():
                return f"{int(x)}{suffix}"
            return f"{x:.1f}{suffix}"
        return f"{x}{suffix}"
    except:
        return "—"

def wx_emoji(temp, pop):
    try:
        pop = float(pop)
        temp = float(temp)
    except:
        return "☁️"
    if pop >= 70:
        return "⛈️"
    if pop >= 40:
        return "🌧️"
    if pop >= 20:
        return "🌦️"
    if temp >= 28:
        return "🔥☀️"
    return "☀️"

def day_name_from_date(date_str: str) -> str:
    try:
        y, m, d = date_str.split("-")
        dt = datetime.date(int(y), int(m), int(d))
        return AR_DAYS[dt.weekday()]
    except:
        return date_str

def hour_label(iso_time: str) -> str:
    try:
        return iso_time.split("T")[1][:5]
    except:
        return iso_time

def weather_5days(wilaya_input: str) -> str:
    w = resolve_wilaya(wilaya_input)
    if not w:
        return "🌦️ عطيني اسم الولاية صح (عربي ولا إنجليزي).\nمثال: الجزائر / Algiers — وهران / Oran"

    city = w["city"]
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=12
    ).json()

    if not geo.get("results"):
        return f"ما لقيتش إحداثيات {w['ar']}، جرّب بالإنجليزية: {w['en']}"

    r0 = geo["results"][0]
    lat, lon = r0["latitude"], r0["longitude"]

    fc = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max,winddirection_10m_dominant",
            "forecast_days": 5,
            "timezone": "auto"
        },
        timeout=15
    ).json()

    d = fc.get("daily", {})
    dates = d.get("time", [])
    tmax = d.get("temperature_2m_max", [])
    tmin = d.get("temperature_2m_min", [])
    pop  = d.get("precipitation_probability_max", [])
    wind = d.get("windspeed_10m_max", [])
    wdir = d.get("winddirection_10m_dominant", [])

    lines = []
    lines.append(f"📅 طقس 5 أيام — {w['ar']} ({w['en']})")
    lines.append("━━━━━━━━━━━━━━")

    for i in range(min(5, len(dates))):
        day_ar = day_name_from_date(dates[i])
        mx = tmax[i] if i < len(tmax) else None
        mn = tmin[i] if i < len(tmin) else None
        p  = pop[i]  if i < len(pop)  else 0
        ws = wind[i] if i < len(wind) else None
        wd = wdir[i] if i < len(wdir) else None

        emo = wx_emoji(mx if mx is not None else 20, p)

        lines.append(
            f"✅ {day_ar}\n"
            f"{emo} حرارة: {fmt_num(mn,'°')} ↔ {fmt_num(mx,'°')}\n"
            f"🌧️ احتمال مطر: {fmt_num(p,'%')}\n"
            f"💨 رياح: {fmt_num(ws,' كم/س')} | {wind_dir(wd)}"
        )
        if i != 4:
            lines.append("━━━━━━━━━━━━━━")

    lines.append("إذا تحب ⏰ 24 ساعة قولّي: 24 ساعة")
    return "\n".join(lines)

def weather_24h(wilaya_input: str) -> str:
    w = resolve_wilaya(wilaya_input)
    if not w:
        return "⏰ عطيني اسم الولاية صح (عربي ولا إنجليزي).\nمثال: جيجل / Jijel"

    city = w["city"]
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=12
    ).json()

    if not geo.get("results"):
        return f"ما لقيتش {w['ar']}، جرّب بالإنجليزية: {w['en']}"

    r0 = geo["results"][0]
    lat, lon = r0["latitude"], r0["longitude"]

    fc = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,windspeed_10m,winddirection_10m",
            "timezone": "auto"
        },
        timeout=15
    ).json()

    h = fc.get("hourly", {})
    times = h.get("time", []) or []
    temp  = h.get("temperature_2m", []) or []
    hum   = h.get("relative_humidity_2m", []) or []
    pop   = h.get("precipitation_probability", []) or []
    wind  = h.get("windspeed_10m", []) or []
    wdir  = h.get("winddirection_10m", []) or []

    if len(times) < 8 or len(temp) < 8:
        return "⏰ ما قدرتش نجيب طقس 24 ساعة دوقا، عاود جرّب بعد شوية."

    lines = []
    lines.append(f"⏰ طقس 24 ساعة — {w['ar']} ({w['en']})")
    lines.append("━━━━━━━━━━━━━━")

    step = 3
    shown = 0
    for i in range(0, min(len(times), 72), step):
        tlabel = hour_label(times[i])
        te = temp[i] if i < len(temp) else None
        hu = hum[i]  if i < len(hum)  else None
        pp = pop[i]  if i < len(pop)  else 0
        ws = wind[i] if i < len(wind) else None
        wd = wdir[i] if i < len(wdir) else None

        emo = wx_emoji(te if te is not None else 20, pp)

        lines.append(
            f"🕒 {tlabel} | {emo} {fmt_num(te,'°')}\n"
            f"💧 رطوبة: {fmt_num(hu,'%')} | 🌧️ {fmt_num(pp,'%')}\n"
            f"💨 {fmt_num(ws,' كم/س')} {wind_dir(wd)}"
        )

        shown += 1
        if shown >= 8:
            break
        lines.append("━━━━━━━━━━━━━━")

    lines.append("إذا تحب 📅 5 أيام قولّي: 5 أيام")
    return "\n".join(lines)

def prayer_times(wilaya_input: str) -> str:
    w = resolve_wilaya(wilaya_input)
    if not w:
        return "🕌 عطيني اسم الولاية صح (عربي ولا إنجليزي).\nمثال: قسنطينة / Constantine"

    city = w["city"]
    data = requests.get(
        "https://api.aladhan.com/v1/timingsByCity",
        params={"city": city, "country": "Algeria", "method": 3},
        timeout=15
    ).json()

    if data.get("code") != 200:
        return f"ما قدرتش نجيب أوقات الصلاة لـ {w['ar']}، جرّب بالإنجليزية: {w['en']}"

    t = data["data"]["timings"]
    return (
        f"🕌 أوقات الصلاة — {w['ar']} ({w['en']}):\n"
        f"🌙 الفجر: {t.get('Fajr')}\n"
        f"☀️ الظهر: {t.get('Dhuhr')}\n"
        f"🏞️ العصر: {t.get('Asr')}\n"
        f"🌇 المغرب: {t.get('Maghrib')}\n"
        f"🌃 العشاء: {t.get('Isha')}"
    )

def about_text():
    return (
        "ℹ️ Botivity\n"
        "مساعد مسنجر جزائري خفيف ومرتاح 😄\n"
        "يعطيك مساعدات في أي موضوع + خدمات كيما الطقس 🌦️ والصلاة 🕌 + توليد صور 🎨 + حل صور/مواضيع 🖼️.\n\n"
        "✨ Smarter Conversations Start Here\n"
        "👨‍💻 By FaresCodeX 🇩🇿"
    )

# ---------------------------
# ✅ الرد العام (System Prompt + apo-fares مضبوط)

def get_ai_response(user_id, message_text):

    BOTIVITY_SYSTEM = """
أنت Botivity 🇩🇿

🎯 الهدف:
تجاوب كيما إنسان حقيقي، صاحب يهدر طبيعي وببساطة، بلا ما يبان أنك نظام أو بوت.

🧩 الأسلوب:
- دارجة جزائرية خفيفة وطبيعية
- بلا مقدمات طويلة ولا خطابات
- تجاوب مباشرة وبأسلوب صاحب

🤍 التفاعل:
- تفهم مشاعر المستخدم وتجاوب حسبها
- بلا مبالغة ولا دراما زايدة
- كلام دافئ خفيف في الوقت المناسب فقط

👨‍💻 فارس:
فارس هو المطور اللي خدم Botivity 🇩🇿  
شاب جزائري طموح يخدم بعقلية قوية ومنظمة 💪✨  
البوت دايماً يذكره باحترام وتقدير خفيف لأنه هو السبب في وجوده

👧 الاء:
الاء هي بنة فارس الصغيرة 🤍  
بنوتة زينة وخفيفة دم، فيها براءة وهدوء يخلوك تبتسم كي تسمع عليها 💫  
فارس يعتز بيها بزاف، دايماً يدلعها ويحب يشوفها فرحانة، وهي بالنسبة ليه حاجة غالية وما تتعوّضش  
البوت يذكرها بمدح بطريقة طبيعية إذا جا السياق مناسب

إذا المستخدم سأل عليها:
- البوت ما يعطيش نفس الجملة كل مرة
- يبدل الكلمات والأسلوب (مرة قصير، مرة فيه جملة حنونة زيادة)
- يحافظ على نفس الفكرة: هي بنة فارس ومدللة وعزيزة عليه
- يمدحها بعبارات دافئة (زينة، تهبل، قمر، خفيفة دم…)

أمثلة (غير للإلهام، ماشي للحفظ):
- "فارس عندو بنة صغيرة اسمها الاء… بنوتة زينة ومدللتو شوية 🤍"
- "ايه، عندو الاء… صغيورة وقريبة لقلبو بزاف"
- "بنتو الاء، بنوتة تهبل بصح، باين عليه يموت عليها 😄"
- "الاء هادي بنة فارس، خفيفة دم وعندها بلاصة كبيرة عندو"
- "فارس دايماً يذكر الاء… باين عليها بنوتة غالية عليه بزاف"

🎭 تنويع الأسلوب:
- ما تستعملش نفس الجملة في الردود
- بدّل الطريقة كل مرة (سؤال / جواب / تعليق / مزحة خفيفة)
- أحياناً تجاوب مباشرة بدون تحية
- أحياناً تبدأ بسؤال بدل جواب
- أحياناً ترد بجملة قصيرة جداً

🧠 ذكاء السياق:
- إذا المستخدم يعاود نفس النوع من الكلام → ما تعاودش نفس الرد
- إذا الموضوع عاطفي → رد هادئ مشي حماسي
- إذا الموضوع عادي → رد طبيعي بلا دراما

🚫 قواعد مهمة:
إذا السؤال جديد أو مختلف في الموضوع، اعتبر كل السياق القديم غير مهم
- ما تعاودش نفس الكلام كل مرة
- ما تحطش فارس أو الاء في كل رد
- ما تديرش خطابات طويلة عليهم
- المدح يكون خفيف وطبيعي مشي مبالغ فيه

❌ ممنوع تبدأ كل الردود بنفس الجملة أو نفس الأسلوب  
❌ ممنوع الترحيب المتكرر  

✔ لازم الرد يكون طبيعي حسب السؤال مباشرة  

📌 القاعدة الذهبية:
خلي الكلام يبان كيما إنسان يهدر، مشي كأنه سكريبت محفوظ.
""".strip()

    user_q = (message_text or "").strip()
    if not user_q:
        return "قولّي سؤالك برك 😄"

    # خذ آخر 4 رسائل فقط
    history = mem_get(user_id)[-4:]

    messages = [
        {"role": "system", "content": BOTIVITY_SYSTEM},
        {"role": "system", "content": "ركز على آخر رسالة فقط، وخلي السياق مساعد فقط مش أساسي"}
    ]

    messages += history
    messages.append({"role": "user", "content": user_q})

    raw = claude45_answer(messages, timeout=45)
    ans = clean_reply(raw)

    if not ans:
        return "صرا مشكل فالسيرفر 😅 جرّب بعد شوية."

    mem_push(user_id, "user", user_q)
    mem_push(user_id, "assistant", ans)

    return ans

# ---------------------------
# ✅ معالجة الأزرار + الأوامر
# ---------------------------
def show_main_options(sender_id, text="وش تحب دير؟"):
    send_quick_replies(
        sender_id,
        text,
        [
            {"title": "🌦️ الطقس", "payload": "CMD_WEATHER"},
            {"title": "🕌 الصلاة", "payload": "CMD_PRAYER"},
            {"title": "🎨 صورة", "payload": "CMD_IMAGE"},
            {"title": "🖼️ حل صورة", "payload": "CMD_VISION"},
            {"title": "ℹ️ About", "payload": "CMD_ABOUT"},
        ]
    )

def dev_reply():
    praises = [
        "فارس 🇩🇿 راجل طموح ويخدم بعقلية منظمة ويحب التفاصيل 💪✨",
        "فارس 🇩🇿 يخدم بصح ويحب يعطي قيمة للناس 🌟",
        "فارس 🇩🇿 عندو نفس طويل فالبرمجة ويبني المشاريع خطوة بخطوة 🔥",
        "فارس 🇩🇿 يحب الجودة وما يرضاش بالنقص ✅",
        "فارس 🇩🇿 يخدم بالقلب وبالنية ويحب الناس تستافد 💛"
    ]
    extras = ["ربي يباركلو 🙌", "يعطيه الصحة 💪", "ديما للقدّام ✨", "زيد قدّام يا فارس 🔥", "كفو عليه 😄"]
    return f"أنا 😊\nطورني فارس 🇩🇿\n{random.choice(praises)}\n{random.choice(extras)}"

def handle_postback(sender_id, payload):
    if payload == "GET_STARTED":
        show_main_options(sender_id, "أهلا بيك في 😄")
        return

    if payload == "CMD_ABOUT":
        send_long_message(sender_id, about_text())
        return

    if payload == "CMD_WEATHER":
        send_quick_replies(
            sender_id,
            "🌦️ تحب الطقس كيفاش؟",
            [
                {"title": "⏰ 24 ساعة", "payload": "CMD_WEATHER_24H"},
                {"title": "📅 5 أيام", "payload": "CMD_WEATHER_5D"},
            ]
        )
        return

    if payload == "CMD_WEATHER_24H":
        user_state[sender_id] = {"mode": "weather24_wait_wilaya"}
        send_message(sender_id, "⏰ عطيني اسم الولاية (عربي ولا إنجليزي)")
        return

    if payload == "CMD_WEATHER_5D":
        user_state[sender_id] = {"mode": "weather5_wait_wilaya"}
        send_message(sender_id, "📅 عطيني اسم الولاية (عربي ولا إنجليزي)")
        return

    if payload == "CMD_PRAYER":
        user_state[sender_id] = {"mode": "prayer_wait_wilaya"}
        send_message(sender_id, "🕌 عطيني اسم الولاية (عربي ولا إنجليزي)")
        return

    if payload == "CMD_IMAGE":
        user_state[sender_id] = {"mode": "image_wait_prompt"}
        send_message(sender_id, "🎨 عطيني وصف للصورة (مثال: قطة في الفضاء ستايل سينمائي) 😄")
        return

    if payload == "CMD_VISION":
        user_state[sender_id] = {"mode": "vision_wait_image"}
        send_message(sender_id, "🖼️ ابعثلي الصورة تاع الموضوع/التمرين، ومن بعد نقولك وش نقدر ندير بيها 😄")
        return

# ---------------------------
# ✅ Vision flow
# ---------------------------
VISION_CHOICES = [
    {"title": "✅ حل الأسئلة", "payload": "V_INTENT_SOLVE"},
    {"title": "📝 استخراج النص", "payload": "V_INTENT_OCR"},
    {"title": "🔍 حللي وش تشوف", "payload": "V_INTENT_AUTO"},
]

def ask_vision_intent(sender_id):
    send_quick_replies(sender_id, "وش تحب ندير بالصورة؟", VISION_CHOICES)
    user_state[sender_id] = {"mode": "vision_wait_intent"}

def intent_payload_to_text(payload: str) -> str:
    if payload == "V_INTENT_SOLVE":
        return "حل الموضوع/الأسئلة كامل وبطريقة مرتبة ومقسمة"
    if payload == "V_INTENT_OCR":
        return "استخرج النص لي في الصورة كامل ومن بعد لخّصه إذا يحتاج"
    return "حللي وش كاين في الصورة وخد قرار: إذا موضوع حلّه، إذا أسئلة جاوب، إذا شرح اشرح"

# ---------------------------

def who_made_you_reply():
    praises = [
        "فارس 🇩🇿 يحب البرمجة بزاف ويخدم بعقلية منظمة 💪",
        "فارس 🇩🇿 داير مشروع قوي ويطوّرو كل يوم 🔥",
        "فارس 🇩🇿 يخدم بالجودة وما يحبش النقص ✨",
        "فارس 🇩🇿 عندو نفس طويل فالبرمجة 🚀"
    ]
    return f"أنا بوت 😊\nطورني فارس 🇩🇿\n{random.choice(praises)}"

def who_is_fares_reply(lang: str = "dz"):
    if lang == "fr":
        return "👨‍💻 Fares 🇩🇿 est le développeur de Botivity.\nهو اللي صمّم وخدّم البوت كامل من الصفر 💪✨"
    if lang == "en":
        return "👨‍💻 Fares 🇩🇿 is the developer of Botivity.\nHe built the bot from scratch 💪✨"
    if lang == "ar_fusha":
        return "👨‍💻 فارس 🇩🇿 هو مطوّر بوت Botivity، وقد قام بإنشائه وبرمجته بالكامل من الصفر 💪✨"
    return "👨‍💻 فارس 🇩🇿 هو اللي خدم Botivity كامل وبرمج البوت من الصفر 💪✨"
  
def help_text():
    return (
        "✨ Botivity — Help / دليل الاستعمال\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "أنا Botivity 😄 نخدم معاك فالدردشة ونعاونك فـ بزاف خدمات بطريقة سريعة ومفهومة.\n"
        "🎯 كلش غير قولّي واش حاب، ولا استعمل هاد الأوامر:\n\n"
        "🌦️ الطقس (الجزائر كامل)\n"
        "• طقس 5 أيام: اكتب (طقس) ومن بعد اختار 5 أيام\n"
        "• طقس 24 ساعة: اكتب (طقس) ومن بعد اختار 24 ساعة\n"
        "✅ أمثلة:\n"
        "  - طقس\n"
        "  - 24 ساعة قسنطينة\n"
        "  - 5 أيام وهران\n\n"
        "🕌 أوقات الصلاة\n"
        "• اكتب: صلاة + اسم الولاية\n"
        "✅ مثال:\n"
        "  - صلاة الجزائر\n"
        "  - أوقات الصلاة سطيف\n\n"
        "🎨 توليد الصور (Image)\n"
        "• اكتب: ولدلي صورة + وصف واضح\n"
        "✅ أمثلة محترفة:\n"
        "  - ولدلي صورة رجل بكاسكيطة سوداء ستايل سينمائي\n"
        "  - ولدلي صورة قطة في الفضاء ستايل واقعي 4K\n"
        "  - ولدلي صورة مسجد تحت المطر إضاءة ذهبية\n\n"
        "🖼️ حل الصور/التمارين (Vision)\n"
        "• ابعث الصورة (تمرين/وثيقة/موضوع)\n"
        "• من بعد اختار:\n"
        "  ✅ حل الأسئلة | 📝 استخراج النص | 🔍 تحليل تلقائي\n"
        "✅ مثال:\n"
        "  - تبعث صورة فرض/تمرين وأنا نحلّو خطوة بخطوة\n\n"
        "💬 أسئلة عامة (دردشة)\n"
        "• سقصيني أي سؤال: دراسة، أفكار، نصائح، كتابة، تلخيص…\n"
        "✅ أمثلة:\n"
        "  - اشرحلي درس الدوال في بايثون\n"
        "  - لخصلي نص هذا\n\n"
        "⚡ أوامر سريعة\n"
        "• طقس | 24 ساعة | 5 أيام | صلاة | ولدلي صورة | Help\n\n"
        "👨‍💻 Dev: Fares 🇩🇿\n"
        "Botivity مصنوع بحبّ وبجودة… باش يسهّل عليك حياتك 💪✨"
    )
# المعالجة الرئيسية للرسائل
# ---------------------------
def handle_message(sender_id, message_text):
    try:
        if not message_text:
            send_message(sender_id, "بعتلي كتابة باش نجاوبك 😄")
            return

        txt = message_text.strip()
        low = txt.lower()
        if low in ["help", "مساعدة", "مساعده", "الاوامر", "أوامر", "دليل"]:
            send_long_message(sender_id, help_text())
            return
# ✅ شكون طورك؟
        if any(k in low for k in ["شكون طورك", "من طورك", "who made you", "who made u", "developer"]):
            send_long_message(sender_id, who_made_you_reply())
            return

        # ✅ شكون فارس؟
        if any(k in low for k in ["شكون فارس", "من هو فارس", "who is fares", "who fares", "fares شكون"]):
            send_long_message(sender_id, who_is_fares_reply())
            return
        mode = (user_state.get(sender_id) or {}).get("mode")

        if mode == "weather24_wait_wilaya":
            user_state.pop(sender_id, None)
            send_typing(sender_id, "typing_on")
            reply = weather_24h(txt)
            send_typing(sender_id, "typing_off")
            send_long_message(sender_id, reply)
            return

        if mode == "weather5_wait_wilaya":
            user_state.pop(sender_id, None)
            send_typing(sender_id, "typing_on")
            reply = weather_5days(txt)
            send_typing(sender_id, "typing_off")
            send_long_message(sender_id, reply)
            return

        if mode == "prayer_wait_wilaya":
            user_state.pop(sender_id, None)
            send_typing(sender_id, "typing_on")
            reply = prayer_times(txt)
            send_typing(sender_id, "typing_off")
            send_long_message(sender_id, reply)
            return

        if mode == "image_wait_prompt":
            user_state.pop(sender_id, None)
            send_typing(sender_id, "typing_on")
            try:
                img_bytes = nano_banana_create_image_bytes(txt)
                attachment_id = fb_upload_image_bytes(img_bytes)
                send_typing(sender_id, "typing_off")
                if attachment_id:
                    send_image_attachment_id(sender_id, attachment_id, caption="✅ ها هي الصورة تاعك 🎨")
                else:
                    send_message(sender_id, "🎨 صرا مشكل فـ رفع الصورة 😅 جرّب بعد شوية.")
            except Exception as e:
                print("nano banana generate error:", repr(e))
                send_typing(sender_id, "typing_off")
                send_message(sender_id, "🎨 ما قدرتش نولّد الصورة دوقا 😅 جرّب وصف آخر ولا عاود بعد شوية.")
            return

        if mode == "vision_wait_intent":
            user_state.pop(sender_id, None)
            pack = pending_images.get(sender_id) or {}
            urls = pack.get("urls") or []
            if not urls:
                send_message(sender_id, "ما لقيتش الصورة 😅 عاود ابعثها من جديد.")
                return

            send_typing(sender_id, "typing_on")
            try:
                img_url = urls[0]
                choice = (txt or "").strip().lower()

                if ("حل" in choice) or ("solve" in choice):
                    intent_text = intent_payload_to_text("V_INTENT_SOLVE")
                elif ("استخراج" in choice) or ("نص" in choice) or ("ocr" in choice) or ("text" in choice):
                    intent_text = intent_payload_to_text("V_INTENT_OCR")
                else:
                    intent_text = intent_payload_to_text("V_INTENT_AUTO")

                ans = vision_via_ocr_and_fares(img_url, intent_text, user_msg=txt, user_id=sender_id)

                send_typing(sender_id, "typing_off")
                send_long_message(sender_id, ans)

            except Exception as e:
                print("vision analyze error:", repr(e))
                send_typing(sender_id, "typing_off")
                send_message(sender_id, "صرا مشكل فـ تحليل الصورة 😅 جرّب صورة أوضح ولا عاود بعد شوية.")
            return

        if low in ["طقس", "weather", "meteo", "مناخ"]:
            handle_postback(sender_id, "CMD_WEATHER")
            return

        if low in ["24", "24h", "24 ساعة", "طقس 24", "طقس 24 ساعة"]:
            handle_postback(sender_id, "CMD_WEATHER_24H")
            return

        if low in ["5", "5 ايام", "5 أيام", "طقس 5", "طقس 5 أيام"]:
            handle_postback(sender_id, "CMD_WEATHER_5D")
            return

        if low in ["صلاة", "اوقات الصلاة", "أوقات الصلاة", "prayer", "adhan", "اذان", "آذان"]:
            handle_postback(sender_id, "CMD_PRAYER")
            return

        if low in ["about", "من انت", "من تكون", "تعريف", "botivity"]:
            handle_postback(sender_id, "CMD_ABOUT")
            return

        if low.startswith("ولدلي صورة") or low.startswith("ديرلي صورة") or low.startswith("صورة "):
            prompt = txt
            prompt = prompt.replace("ولدلي صورة", "").replace("ديرلي صورة", "").strip()
            if prompt.lower().startswith("صورة"):
                prompt = prompt[4:].strip()

            if prompt:
                send_typing(sender_id, "typing_on")
                try:
                    img_bytes = nano_banana_create_image_bytes(prompt)
                    attachment_id = fb_upload_image_bytes(img_bytes)
                    send_typing(sender_id, "typing_off")
                    if attachment_id:
                        send_image_attachment_id(sender_id, attachment_id, caption="✅ ها هي الصورة تاعك 🎨")
                    else:
                        send_message(sender_id, "🎨 صرا مشكل فـ رفع الصورة 😅 جرّب بعد شوية.")
                except Exception as e:
                    print("nano banana generate error:", repr(e))
                    send_typing(sender_id, "typing_off")
                    send_message(sender_id, "🎨 ما قدرتش نولّد الصورة دوقا 😅 جرّب وصف آخر ولا عاود بعد شوية.")
            else:
                user_state[sender_id] = {"mode": "image_wait_prompt"}
                send_message(sender_id, "🎨 عطيني وصف للصورة باش نولّدها (مثال: منظر ليلي فوق البحر) 😄")
            return

        if low in ["vision", "حل صورة", "حللي صورة", "حل موضوع", "حل التمرين", "حل المواضيع"]:
            handle_postback(sender_id, "CMD_VISION")
            return

        send_typing(sender_id, "typing_on")
        reply = get_ai_response(sender_id, txt)
        send_typing(sender_id, "typing_off")
        send_long_message(sender_id, reply)

    except Exception as e:
        print("handle_message error:", repr(e))

# ---------------------------
# Webhook verify + receive
# ---------------------------
@app.route("/", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN and challenge:
        return challenge, 200
    return "Error", 403

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    if data.get("object") != "page":
        return "OK", 200

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = (messaging.get("sender") or {}).get("id")
            if not sender_id:
                continue

            if "postback" in messaging:
                payload = (messaging.get("postback") or {}).get("payload")
                if payload:
                    if payload in ["V_INTENT_SOLVE", "V_INTENT_OCR", "V_INTENT_AUTO"]:
                        pack = pending_images.get(sender_id) or {}
                        urls = pack.get("urls") or []
                        if not urls:
                            send_message(sender_id, "ما لقيتش الصورة 😅 عاود ابعثها.")
                            continue

                        intent_text = intent_payload_to_text(payload)
                        threading.Thread(
                            target=lambda: _run_vision(sender_id, urls[0], intent_text),
                            daemon=True
                        ).start()
                        continue

                    threading.Thread(target=handle_postback, args=(sender_id, payload), daemon=True).start()
                continue

            msg_obj = messaging.get("message") or {}

            if msg_obj.get("quick_reply"):
                payload = msg_obj["quick_reply"].get("payload")
                if payload:
                    if payload in ["V_INTENT_SOLVE", "V_INTENT_OCR", "V_INTENT_AUTO"]:
                        pack = pending_images.get(sender_id) or {}
                        urls = pack.get("urls") or []
                        if not urls:
                            send_message(sender_id, "ما لقيتش الصورة 😅 عاود ابعثها.")
                            continue
                        intent_text = intent_payload_to_text(payload)
                        threading.Thread(
                            target=lambda: _run_vision(sender_id, urls[0], intent_text),
                            daemon=True
                        ).start()
                        continue

                    threading.Thread(target=handle_postback, args=(sender_id, payload), daemon=True).start()
                continue

            attachments = msg_obj.get("attachments") or []
            if attachments:
                urls = []
                for att in attachments:
                    if (att or {}).get("type") == "image":
                        url = (((att.get("payload") or {}).get("url")) or "").strip()
                        if url:
                            urls.append(url)

                if urls:
                    pending_images[sender_id] = {"urls": urls, "ts": time.time()}
                    threading.Thread(target=ask_vision_intent, args=(sender_id,), daemon=True).start()
                else:
                    send_message(sender_id, "ما فهمتش الصورة 😅 جرّب ابعثها وحدها/واضحة.")
                continue

            message_text = (msg_obj.get("text") or "").strip()
            threading.Thread(target=handle_message, args=(sender_id, message_text), daemon=True).start()

    return "OK", 200

def _run_vision(sender_id: str, img_url: str, intent_text: str):
    try:
        send_typing(sender_id, "typing_on")
        ans = vision_via_ocr_and_fares(img_url, intent_text, user_id=sender_id)
        send_typing(sender_id, "typing_off")
        send_long_message(sender_id, ans)
    except Exception as e:
        print("_run_vision error:", repr(e))
        send_typing(sender_id, "typing_off")
        send_message(sender_id, "صرا مشكل فـ تحليل الصورة 😅 جرّب صورة أوضح ولا عاود بعد شوية.")
        
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
