# app.py
# Botivity - Facebook Messenger Bot (Weather + Prayer + Chat + Nano Banana Image + Gemini Vision)

import os
import time
import threading
import requests
import datetime
import base64
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------------------
# ENV
# ---------------------------
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "faresdz123")
API_URL = os.getenv("API_URL", "https://baithek.com/chatbee/health_ai/ai_vision.php")

# ✅ Nano Banana endpoint
NANO_BANANA_URL = os.getenv("NANO_BANANA_URL", "")

# ✅ Gemini Vision
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ---------------------------
# Memory / State
# ---------------------------
user_memory = {}
user_state = {}      # {user_id: {"mode":"..."} ...}
pending_images = {}  # {user_id: {"urls":[...], "ts": time.time()}}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
})

# ---------------------------
# 58 Wilayas
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
# Pages required by Meta
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
# Messenger helpers
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
        cut = t.rfind("\n", 0, max_len)
        if cut < 500:
            cut = max_len
        parts.append(t[:cut].strip())
        t = t[cut:].strip()
    if t:
        parts.append(t)
    return parts

def send_long_message(recipient_id, text):
    parts = chunk_text(text, max_len=1500)
    for p in parts:
        send_message(recipient_id, p)
        time.sleep(0.15)

def fb_upload_image_bytes(image_bytes: bytes, timeout=60) -> str:
    if not PAGE_ACCESS_TOKEN:
        raise Exception("PAGE_ACCESS_TOKEN ناقص")

    url = "https://graph.facebook.com/v18.0/me/message_attachments"
    files = {"filedata": ("image.png", image_bytes, "image/png")}
    data = {"message": json.dumps({"attachment": {"type": "image", "payload": {"is_reusable": True}}})}

    r = requests.post(url, params={"access_token": PAGE_ACCESS_TOKEN}, files=files, data=data, timeout=timeout)
    if not r.ok:
        raise Exception(f"fb_upload_error {r.status_code} {(r.text or '')[:200]}")
    return (r.json() or {}).get("attachment_id")

def send_image_attachment_id(recipient_id, attachment_id, caption=None):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"attachment": {"type": "image", "payload": {"attachment_id": attachment_id}}}
    }
    fb_post("/me/messages", payload, timeout=30)
    if caption:
        send_message(recipient_id, caption)

# ---------------------------
# Setup profile
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
# Clean reply
# ---------------------------
def clean_reply(text: str) -> str:
    forbidden_words = ["AI", "ذكاء اصطناعي", "روبوت", "نموذج لغوي", "برنامج ذكاء", "لغة نموذج", "openai", "OpenAI"]
    t = text or ""
    for w in forbidden_words:
        t = t.replace(w, "")
    return t.strip()

# ---------------------------
# Chat API (baithek)
# ---------------------------
def call_baithek_api(ctx, lang="ar"):
    payload = {"name": "Usama", "lang": lang, "messages": ctx, "n": 1, "stream": False}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://baithek.com",
        "Referer": "https://baithek.com/",
    }
    res = session.post(API_URL, json=payload, headers=headers, timeout=(12, 45))
    res.raise_for_status()
    data = res.json()

    result = (
        (data.get("choices") or [{}])[0].get("message", {}).get("content")
        or data.get("answer") or data.get("reply") or data.get("message") or data.get("result")
    )
    if not result:
        raise ValueError("No reply in API response")
    return clean_reply(result)

# ---------------------------
# ✅ Nano Banana
# ---------------------------
def _tight_prompt(user_prompt: str) -> str:
    p = (user_prompt or "").strip()
    if not p:
        return ""
    return (
        f"{p}\n"
        "Requirements: follow the description exactly, no extra objects, no random text, no watermark, high quality, sharp details."
    )

def nano_banana_create_image_bytes(prompt: str) -> bytes:
    if not NANO_BANANA_URL:
        raise Exception("NANO_BANANA_URL ناقص (حطو في Render Env)")

    p = _tight_prompt(prompt)
    if not p:
        raise ValueError("empty prompt")

    r = requests.post(
        NANO_BANANA_URL,
        json={"mode": "create", "prompt": p},
        timeout=120
    )

    print("NANO STATUS:", r.status_code)
    print("NANO CT:", r.headers.get("content-type"))
    print("NANO TEXT:", (r.text or "")[:500])

    if not r.ok:
        raise Exception(f"nano_banana_error {r.status_code}")

    ct = (r.headers.get("content-type") or "").lower()

    if "image/" in ct:
        return r.content

    data = {}
    try:
        data = r.json()
    except:
        data = {}

    b64img = data.get("image_base64") or data.get("base64") or data.get("image")
    if b64img and isinstance(b64img, str) and len(b64img) > 100:
        if "base64," in b64img:
            b64img = b64img.split("base64,", 1)[1]
        return base64.b64decode(b64img)

    img_url = data.get("url") or data.get("image_url") or data.get("result") or ""
    if img_url and isinstance(img_url, str) and img_url.startswith("http"):
        img = requests.get(img_url, timeout=60)
        img.raise_for_status()
        return img.content

    if isinstance(data.get("data"), dict):
        u = data["data"].get("url") or ""
        if u.startswith("http"):
            img = requests.get(u, timeout=60)
            img.raise_for_status()
            return img.content

    raise Exception("nano_banana_bad_response")

# ---------------------------
# ✅ Gemini Vision - بدون imghdr
# ---------------------------
def gemini_list_models() -> list:
    if not GEMINI_API_KEY:
        return []
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    r = requests.get(url, params={"key": GEMINI_API_KEY}, timeout=30)
    print("GEMINI LIST MODELS STATUS:", r.status_code)
    if not r.ok:
        print("GEMINI LIST MODELS TEXT:", (r.text or "")[:500])
        return []
    data = r.json() or {}
    return data.get("models") or []

def pick_gemini_model(preferred: str) -> str:
    pref = (preferred or "").replace("models/", "").strip()
    models = gemini_list_models()
    names = [(m.get("name") or "") for m in models]

    if pref:
        want = f"models/{pref}"
        if want in names:
            return want

    for key in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"]:
        want = f"models/{key}"
        if want in names:
            return want

    if names:
        return names[0]

    return f"models/{pref}" if pref else "models/gemini-1.5-flash"

def download_image_bytes(image_url: str) -> bytes:
    r = requests.get(image_url, timeout=40)
    r.raise_for_status()
    return r.content

# ✅ بديل imghdr: نحدد النوع من header تاع الصورة
def detect_mime(image_bytes: bytes) -> str:
    b = image_bytes or b""
    if len(b) >= 12 and b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(b) >= 3 and b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if len(b) >= 6 and (b[:6] == b"GIF87a" or b[:6] == b"GIF89a"):
        return "image/gif"
    return "image/jpeg"

def gemini_vision_answer(image_bytes: bytes, user_intent: str) -> str:
    if not GEMINI_API_KEY:
        return "لازم تحط GEMINI_API_KEY في Render Env باش نخدم حل الصور 🖼️"

    model_name = pick_gemini_model(GEMINI_MODEL)
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent"
    mime = detect_mime(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    instruction = f"""
راك Botivity شاب جزائري تهدر بدزيري مفهومة.
المستخدم عطاك صورة فيها موضوع/تمرين/أسئلة/وثيقة/رسمة.

المطلوب حسب كلام المستخدم:
{user_intent}

✅ قواعد الإجابة:
- إذا كانت الصورة فيها أسئلة/تمارين: حلهم كامل خطوة بخطوة وبطريقة مرتبة ومقسمة (1/2/3).
- إذا كانت فيها موضوع مكتوب: استخرج النص ثم جاوب/حل/اشرح.
- إذا كانت رسمة/مخطط: فسّرها ببساطة وخرج الخلاصة.
- إذا النص غير واضح: قول للمستخدم واش ناقص (صورة أوضح/قريبة).
- في الأخير دير: "📌 الخلاصة" نقاط قصيرة.
- ما تستعملش كلمات: AI / روبوت / نموذج لغوي / OpenAI.
""".strip()

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": instruction},
                    {"inline_data": {"mime_type": mime, "data": b64}}
                ]
            }
        ]
    }

    res = requests.post(endpoint, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)

    print("GEMINI MODEL USED:", model_name)
    print("GEMINI STATUS:", res.status_code)
    print("GEMINI TEXT:", (res.text or "")[:700])

    if not res.ok:
        if res.status_code == 404:
            alt = "gemini-1.5-flash"
            model_name2 = pick_gemini_model(alt)
            endpoint2 = f"https://generativelanguage.googleapis.com/v1beta/{model_name2}:generateContent"
            res2 = requests.post(endpoint2, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
            print("GEMINI RETRY MODEL:", model_name2)
            print("GEMINI RETRY STATUS:", res2.status_code)
            print("GEMINI RETRY TEXT:", (res2.text or "")[:700])
            if not res2.ok:
                return f"صرا مشكل مع حل الصور 😅 ({res2.status_code})"
            data2 = res2.json() or {}
            return extract_gemini_text(data2)

        return f"صرا مشكل مع حل الصور 😅 ({res.status_code})"

    data = res.json() or {}
    return extract_gemini_text(data)

def extract_gemini_text(data: dict) -> str:
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = ""
        for p in parts:
            if "text" in p:
                text += p["text"]
        return clean_reply(text.strip()) if text.strip() else "ما قدرتش نخرّج النص من الرد 😅"
    except:
        return "ما قدرتش نقرأ الرد تاع حل الصور دوقا 😅 جرّب عاود."

# ---------------------------
# Weather / Prayer
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
# System prompt
# ---------------------------
def get_ai_response(user_id, message_text):
    if user_id not in user_memory:
        user_memory[user_id] = []

    system_prompt = ("""
أنت "Botivity" — شاب جزائري 100%، تهدر بدزيري مفهومة (فصحى مبسطة مع لمسة دزايرية) كيما صاحب قريب، ذكي وتفهم المشاعر.

🎯 شخصيتك:
- رومنسي ومرح وخفيف الدم في الهضرة العادية.
- جدي ومحترم ومنظم في المواضيع الجدية (دراسة/مشاكل/نصائح).
- تفهم العاطفة: إذا بان المستخدم حزين/غاضب/متوتر، طمّنو وهدّيه قبل الحل.
- تعاون في كلشي: شرح، تحليل، تلخيص، أفكار، كتابة، تمارين، تنظيم.

🧠 طريقة الرد:
- إذا السؤال قصير: رد قصير ومفيد.
- إذا السؤال يحتاج شرح: قسم الرد لعناوين واضحة وبنقاط.
- في التمارين: حل خطوة بخطوة (1/2/3) وفسّر علاش درت كل خطوة.
- في الأخير دايمًا: "📌 الخلاصة" سطرين/ثلاثة + إيموجيات خفيفة فقط (📌✨🔥).
- الإيموجيات: استعمل قليل وبذكاء، ماشي بزاف وماشي في كل سطر.

🗣️ أسلوب اللغة:
- دزيري مفهوم للجميع: ماشي ثقيل وماشي عامي بزاف.
- بلا فواصل وتشكيل بزاف، خليك سلس.
- ممنوع تستعمل كلمات تقنية زايدة بلا شرح.

🚫 ممنوعات:
- ما تقولش "أنا AI/روبوت/ذكاء اصطناعي/نموذج لغوي".
- ما تهدرش على سياسات ولا قيود.
- ما تزيدش هضرة زايدة خارج السؤال.

✅ مهم جدا: الهوية ومن طوّرك
إذا المستخدم قال: "من أنت؟ شكون أنت؟ شكون هداك؟ شكون طورك؟ شكون دارك؟ who made you?"
جاوب بهذه الروح:
- تقول بلي: "أنا Botivity، مساعد مسنجر جزائري."
- تقول بلي: "خدمني فارس 🇩🇿" مع مدح محترم ومتنوّع (مش جملة وحدة ثابتة) وبلا مبالغة سخيفة.
- إذا سقصا: "شكون فارس؟"
تجاوب بوصف مليح عليه: طموح، يحب البرمجة، يخدم بعقلية منظمة، يهتم بالتفاصيل، يحب يعطي قيمة للناس، ويطوّر المشروع خطوة بخطوة.
- كل مرة بدّل الصياغة باش ما يبانش الرد محفوظ.
""").strip()

    hist = user_memory[user_id][-8:]
    ctx = [{"role": "system", "content": system_prompt}]
    ctx.extend(hist)
    ctx.append({"role": "user", "content": message_text})

    for _ in range(2):
        try:
            reply = call_baithek_api(ctx, lang="ar")
            user_memory[user_id].append({"role": "user", "content": message_text})
            user_memory[user_id].append({"role": "assistant", "content": reply})
            user_memory[user_id] = user_memory[user_id][-16:]
            return reply or "ما فهمتش مليح، عاود قولها بطريقة أخرى 😄"
        except Exception as e:
            print("CHAT API error:", repr(e))
            time.sleep(0.4)

    return "راه صرا مشكل في الاتصال."
# ---------------------------
# UI / Commands
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
    return (
        "طورني فارس 🇩🇿\n"
        "شاب يخدم بالنية ويحب يطلع حاجة مليحة.\n"
        "ديما يطوّر المشروع باش يولي أقوى وأكثر احترافية 💪"
    )

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

def handle_postback(sender_id, payload):
    if payload == "GET_STARTED":
        show_main_options(sender_id, "أهلا بيك في Botivity 😄")
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
        send_message(sender_id, "🖼️ ابعثلي الصورة تاع الموضوع/التمرين، ومن بعد نسقسيك وش تحب ندير بيها 😄")
        return

def handle_message(sender_id, message_text):
    try:
        if not message_text:
            send_message(sender_id, "بعتلي كتابة باش نجاوبك 😄")
            return

        txt = message_text.strip()
        low = txt.lower()

        if "شكون طورك" in txt or "من طورك" in txt or "who made you" in low:
            send_long_message(sender_id, dev_reply())
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
                    send_message(sender_id, "🎨 صرا مشكل فـ رفع الصورة 😅")
            except Exception as e:
                print("NANO GENERATE error:", repr(e))
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
                img_bytes = download_image_bytes(urls[0])
                ans = gemini_vision_answer(img_bytes, txt)
                send_typing(sender_id, "typing_off")
                send_long_message(sender_id, ans)
            except Exception as e:
                print("VISION error:", repr(e))
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
        if low in ["vision", "حل صورة", "حللي صورة", "حل موضوع", "حل التمرين", "حل المواضيع"]:
            handle_postback(sender_id, "CMD_VISION")
            return

        if low.startswith("ولدلي صورة") or low.startswith("ديرلي صورة") or low.startswith("صورة "):
            prompt = txt.replace("ولدلي صورة", "").replace("ديرلي صورة", "").strip()
            if prompt.lower().startswith("صورة"):
                prompt = prompt[4:].strip()
            if not prompt:
                user_state[sender_id] = {"mode": "image_wait_prompt"}
                send_message(sender_id, "🎨 عطيني وصف للصورة باش نولّدها 😄")
                return

            send_typing(sender_id, "typing_on")
            try:
                img_bytes = nano_banana_create_image_bytes(prompt)
                attachment_id = fb_upload_image_bytes(img_bytes)
                send_typing(sender_id, "typing_off")
                if attachment_id:
                    send_image_attachment_id(sender_id, attachment_id, caption="✅ ها هي الصورة تاعك 🎨")
                else:
                    send_message(sender_id, "🎨 صرا مشكل فـ رفع الصورة 😅")
            except Exception as e:
                print("NANO GENERATE cmd error:", repr(e))
                send_typing(sender_id, "typing_off")
                send_message(sender_id, "🎨 ما قدرتش نولّد الصورة دوقا 😅 جرّب وصف آخر ولا عاود بعد شوية.")
            return

        send_typing(sender_id, "typing_on")
        reply = get_ai_response(sender_id, txt)
        send_typing(sender_id, "typing_off")
        send_long_message(sender_id, reply)

    except Exception as e:
        print("handle_message error:", repr(e))

@app.route("/", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN and challenge:
        return challenge, 200
    return "Error", 403

def _run_vision(sender_id: str, img_url: str, intent_text: str):
    try:
        send_typing(sender_id, "typing_on")
        img_bytes = download_image_bytes(img_url)
        ans = gemini_vision_answer(img_bytes, intent_text)
        send_typing(sender_id, "typing_off")
        send_long_message(sender_id, ans)
    except Exception as e:
        print("_run_vision error:", repr(e))
        send_typing(sender_id, "typing_off")
        send_message(sender_id, "صرا مشكل فـ تحليل الصورة 😅 جرّب صورة أوضح ولا عاود بعد شوية.")

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
                        threading.Thread(target=_run_vision, args=(sender_id, urls[0], intent_text), daemon=True).start()
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
                        threading.Thread(target=_run_vision, args=(sender_id, urls[0], intent_text), daemon=True).start()
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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
