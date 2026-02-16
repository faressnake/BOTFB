import os
import time
import queue
import requests
import threading
from flask import Flask, request

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "faresdz123")
API_URL = os.getenv("API_URL", "https://baithek.com/chatbee/health_ai/ai_vision.php")

user_memory = {}
user_state = {}   # sender_id -> {"mode": "weather_wait_city"} / "prayer_wait_city"

jobs = queue.Queue(maxsize=500)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
})

WILAYAS = {
  "أدرار":"Adrar","الشلف":"Chlef","الأغواط":"Laghouat","أم البواقي":"Oum El Bouaghi","باتنة":"Batna","بجاية":"Bejaia",
  "بسكرة":"Biskra","بشار":"Bechar","البليدة":"Blida","البويرة":"Bouira","تمنراست":"Tamanrasset","تبسة":"Tebessa",
  "تلمسان":"Tlemcen","تيارت":"Tiaret","تيزي وزو":"Tizi Ouzou","الجزائر":"Algiers","الجلفة":"Djelfa","جيجل":"Jijel",
  "سطيف":"Setif","سعيدة":"Saida","سكيكدة":"Skikda","سيدي بلعباس":"Sidi Bel Abbes","عنابة":"Annaba","قالمة":"Guelma",
  "قسنطينة":"Constantine","المدية":"Medea","مستغانم":"Mostaganem","المسيلة":"M'Sila","معسكر":"Mascara","ورقلة":"Ouargla",
  "وهران":"Oran","البيض":"El Bayadh","إليزي":"Illizi","برج بوعريريج":"Bordj Bou Arreridj","بومرداس":"Boumerdes",
  "الطارف":"El Tarf","تندوف":"Tindouf","تيسمسيلت":"Tissemsilt","الوادي":"El Oued","خنشلة":"Khenchela","سوق أهراس":"Souk Ahras",
  "تيبازة":"Tipaza","ميلة":"Mila","عين الدفلى":"Ain Defla","النعامة":"Naama","عين تموشنت":"Ain Temouchent",
  "غرداية":"Ghardaia","غليزان":"Relizane",
  "تيميمون":"Timimoun","برج باجي مختار":"Bordj Badji Mokhtar","أولاد جلال":"Ouled Djellal","بني عباس":"Beni Abbes",
  "إن صالح":"In Salah","إن قزام":"In Guezzam","تقرت":"Touggourt","جانت":"Djanet","المغير":"El M'Ghair","المنيعة":"El Meniaa"
}
WILAYAS_EN = {v.lower(): v for v in WILAYAS.values()}

DAY_AR = ["الأحد","الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت"]

def resolve_wilaya(user_text: str):
    t = (user_text or "").strip()
    if not t:
        return None
    tl = t.lower()
    if t in WILAYAS:
        return WILAYAS[t]
    if tl in WILAYAS_EN:
        return WILAYAS_EN[tl]
    t2 = tl.replace("’","").replace("'","").replace("-"," ").replace("  "," ")
    for ar, en in WILAYAS.items():
        if t2 == en.lower():
            return en
    return None

def fb_post(payload, timeout=15):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try:
        requests.post(url, json=payload, timeout=timeout)
    except:
        pass

def send_typing(recipient_id, action="typing_on"):
    fb_post({"recipient": {"id": recipient_id}, "sender_action": action}, timeout=5)

def send_message(recipient_id, text):
    fb_post({"recipient": {"id": recipient_id}, "message": {"text": text}}, timeout=15)

@app.route("/test", methods=["GET"])
def test():
    return "السيرفر راه يخدم 😎🔥", 200

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

def setup_persistent_menu():
    if not PAGE_ACCESS_TOKEN:
        return "Missing PAGE_ACCESS_TOKEN"
    url = f"https://graph.facebook.com/v18.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "get_started": {"payload": "GET_STARTED"},
        "persistent_menu": [{
            "locale": "default",
            "composer_input_disabled": False,
            "call_to_actions": [
                {"type": "postback", "title": "🌦️ الطقس", "payload": "MENU_WEATHER"},
                {"type": "postback", "title": "🕌 أوقات الصلاة", "payload": "MENU_PRAYER"},
                {"type": "postback", "title": "ℹ️ About", "payload": "MENU_ABOUT"}
            ]
        }]
    }
    r = requests.post(url, json=payload, timeout=20)
    return f"{r.status_code} {r.text[:500]}"

@app.route("/setup", methods=["GET"])
def setup():
    return setup_persistent_menu(), 200

def clean_reply(text: str) -> str:
    forbidden_words = ["AI", "ذكاء اصطناعي", "روبوت", "نموذج لغوي", "برنامج ذكاء", "لغة نموذج", "openai"]
    t = (text or "")
    for w in forbidden_words:
        t = t.replace(w, "")
    return t.strip()

def call_baithek_api(ctx, lang="ar"):
    payload = {"name": "Usama", "lang": lang, "messages": ctx, "n": 1, "stream": False}
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://baithek.com",
        "Referer": "https://baithek.com/",
    }
    res = session.post(API_URL, json=payload, headers=headers, timeout=(12, 35))
    res.raise_for_status()
    data = res.json()
    result = (
        (data.get("choices") or [{}])[0].get("message", {}).get("content")
        or data.get("answer") or data.get("reply") or data.get("message") or data.get("result")
    )
    if not result:
        raise ValueError("No reply in API response")
    return clean_reply(result)

def system_prompt():
    return (
        "راك خويا/أختي 😄☕ نهدر معاك بدزيرية طبيعية.\n"
        "نعاونك فكلش (دراسة/نصائح/تقنية/حياة…) وبطريقة مفهومة.\n"
        "سؤال قصير = رد قصير، سؤال يحتاج شرح = نقاط + مثال.\n"
        "استعمل ايموجيات في بلاصتهم 😂🔥💪☕\n"
        "ممنوع تقول بلي انت AI ولا تذكر ذكاء اصطناعي.\n"
        "إذا تسقساوك شكون طورك جاوب فقط: \"طورني فارس 🇩🇿 شاب جزائري خطير ونفتخر بيه 🔥\""
    )

def get_ai_response(user_id, message_text):
    if user_id not in user_memory:
        user_memory[user_id] = []
    hist = user_memory[user_id][-6:]
    ctx = [{"role": "system", "content": system_prompt()}] + hist + [{"role": "user", "content": message_text}]
    reply = call_baithek_api(ctx, lang="ar")
    user_memory[user_id].append({"role": "user", "content": message_text})
    user_memory[user_id].append({"role": "assistant", "content": reply})
    user_memory[user_id] = user_memory[user_id][-14:]
    return reply if reply else "سمحلي خويا ما فهمتش مليح 😅"

def wx_emoji(rain_mm, wind_kmh, tmax):
    if rain_mm >= 8: return "⛈️"
    if rain_mm >= 1: return "🌧️"
    if wind_kmh >= 35: return "🌬️"
    if tmax >= 32: return "🌞"
    return "⛅"

def get_weather_5days(wilaya_en: str):
    geo = session.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": f"{wilaya_en}, Algeria", "count": 1, "language": "en", "format": "json"},
        timeout=15
    ).json()
    results = (geo.get("results") or [])
    if not results:
        return None

    lat = results[0]["latitude"]; lon = results[0]["longitude"]
    fc = session.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
            "timezone": "Africa/Algiers"
        },
        timeout=20
    ).json()

    d = fc.get("daily") or {}
    times = d.get("time", [])[:5]
    tmax = d.get("temperature_2m_max", [])[:5]
    tmin = d.get("temperature_2m_min", [])[:5]
    rain = d.get("precipitation_sum", [])[:5]
    wind = d.get("windspeed_10m_max", [])[:5]

    lines = [f"🌦️ طقس **{wilaya_en}** (5 أيام) 👇"]
    base = (time.gmtime().tm_wday + 1) % 7
    for i in range(len(times)):
        emoji = wx_emoji(rain[i], wind[i], tmax[i])
        lines.append(
            f"{emoji} {DAY_AR[(base+i)%7]}: {int(tmax[i])}°/{int(tmin[i])}° | 💨 {int(wind[i])}km/h | 🌧️ {rain[i]}mm"
        )
    lines.append("✍️ اكتب ولاية أخرى إذا تحب 😉")
    return "\n".join(lines)

def get_prayer_times(wilaya_en: str):
    r = session.get(
        "https://api.aladhan.com/v1/timingsByCity",
        params={"city": wilaya_en, "country": "Algeria", "method": 3},
        timeout=20
    ).json()
    data = (r.get("data") or {})
    timings = (data.get("timings") or {})
    if not timings:
        return None

    return (
        f"🕌 مواقيت الصلاة في **{wilaya_en}** 👇\n"
        f"🌙 الفجر: {timings.get('Fajr')}\n"
        f"🌅 الشروق: {timings.get('Sunrise')}\n"
        f"☀️ الظهر: {timings.get('Dhuhr')}\n"
        f"🌤️ العصر: {timings.get('Asr')}\n"
        f"🌇 المغرب: {timings.get('Maghrib')}\n"
        f"🌃 العشاء: {timings.get('Isha')}\n\n"
        f"✍️ اكتب ولاية أخرى إذا تحب 😉"
    )

def about_text():
    return (
        "ℹ️ Botivity™\n"
        "مساعد مسنجر دزيري 😄☕ يعاونك فكلش: دراسة 📚، نصائح 💡، تقنية 💻، أفكار مشاريع 🚀.\n\n"
        "🔥 سريع ومرح ومنظم.\n"
        "👨‍💻 المطور: Fares (FaresCodeX) 🇩🇿🔥"
    )

def handle_postback(sender_id, payload):
    if payload == "GET_STARTED":
        send_message(sender_id, "مرحبا بيك في Botivity™ 😄\nاختار من المينو: 🌦️ الطقس / 🕌 الصلاة / ℹ️ About")
        return

    if payload == "MENU_WEATHER":
        user_state[sender_id] = {"mode": "weather_wait_city"}
        send_message(sender_id, "🌦️ عطيلي اسم الولاية (عربي ولا انجليزي) مثال: وهران / Oran 😉")
        return

    if payload == "MENU_PRAYER":
        user_state[sender_id] = {"mode": "prayer_wait_city"}
        send_message(sender_id, "🕌 عطيلي اسم الولاية باش نجيب مواقيت الصلاة (مثال: الجزائر / Algiers) 😊")
        return

    if payload == "MENU_ABOUT":
        send_message(sender_id, about_text())
        return

def process_message(sender_id, message_text):
    try:
        if not message_text:
            send_message(sender_id, "بعتلي كتابة برك باش نجاوبك 😄✍️")
            return

        # حالات خاصة
        if message_text.startswith("__POSTBACK__:"):
            payload = message_text.split(":", 1)[1]
            handle_postback(sender_id, payload)
            return

        # طلب مطور
        if "شكون طورك" in message_text:
            send_message(sender_id, "طورني فارس 🇩🇿 شاب جزائري خطير و نفتخر بيه 🔥")
            return

        # إذا راه يستنى ولاية
        st = user_state.get(sender_id, {}).get("mode")
        if st == "weather_wait_city":
            w = resolve_wilaya(message_text) or message_text.strip()
            user_state.pop(sender_id, None)
            wx = get_weather_5days(w)
            send_message(sender_id, wx or "ما لقيتش هذي الولاية 😅 جرّب: Oran / وهران")
            return

        if st == "prayer_wait_city":
            w = resolve_wilaya(message_text) or message_text.strip()
            user_state.pop(sender_id, None)
            pt = get_prayer_times(w)
            send_message(sender_id, pt or "ما لقيتش هذي الولاية 😅 جرّب: Algiers / الجزائر")
            return

        # رد سريع + typing
        send_typing(sender_id, "typing_on")
        # reply AI
        reply = get_ai_response(sender_id, message_text)
        send_typing(sender_id, "typing_off")
        send_message(sender_id, reply)

    except Exception as e:
        send_message(sender_id, "سمحلي صرا مشكل صغير 😅 عاود بعد لحظة.")
        print("process_message error:", repr(e))

def worker_loop():
    while True:
        sender_id, text = jobs.get()
        try:
            process_message(sender_id, text)
        finally:
            jobs.task_done()

threading.Thread(target=worker_loop, daemon=True).start()

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

            postback = messaging.get("postback") or {}
            if postback.get("payload"):
                payload = postback["payload"]
                if not jobs.full():
                    jobs.put((sender_id, f"__POSTBACK__:{payload}"))
                continue

            msg_obj = messaging.get("message") or {}
            message_text = (msg_obj.get("text") or "").strip()

            if not jobs.full():
                jobs.put((sender_id, message_text))

    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
