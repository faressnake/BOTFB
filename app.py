import os
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "faresdz123")
API_URL = os.getenv("API_URL", "https://baithek.com/chatbee/health_ai/ai_vision.php")

# Memory خفيفة + حالة بسيطة للأوامر (طقس/صلاة)
user_memory = {}
user_state = {}  # {user_id: {"mode":"weather_wait_city"} ...}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
})

# ---------------------------
# صفحات ضرورية لفيسبوك
# ---------------------------
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
    if not PAGE_ACCESS_TOKEN:
        return
    payload = {"recipient": {"id": recipient_id}, "sender_action": action}
    fb_post("/me/messages", payload, timeout=10)

def send_message(recipient_id, text):
    if not PAGE_ACCESS_TOKEN:
        return
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    fb_post("/me/messages", payload, timeout=20)

def send_quick_replies(recipient_id, text, replies):
    """
    replies = [{"title":"🌦️ الطقس","payload":"CMD_WEATHER"}, ...]
    """
    if not PAGE_ACCESS_TOKEN:
        return
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

# ---------------------------
# ✅ Setup الحقيقي (Get Started + Persistent Menu)
# ---------------------------
def setup_messenger_profile():
    # Get Started + Persistent Menu
    profile_payload = {
        "get_started": {"payload": "GET_STARTED"},
        "persistent_menu": [
            {
                "locale": "default",
                "composer_input_disabled": False,
                "call_to_actions": [
                    {"type": "postback", "title": "🌦️ الطقس", "payload": "CMD_WEATHER"},
                    {"type": "postback", "title": "🕌 أوقات الصلاة", "payload": "CMD_PRAYER"},
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
    # باش تشوف واش صار في Render logs
    print("SETUP RESULT:", result)
    return jsonify(result), (200 if result.get("ok") else 500)

# ---------------------------
# تنظيف الرد من كلمات
# ---------------------------
def clean_reply(text: str) -> str:
    forbidden_words = ["AI", "ذكاء اصطناعي", "روبوت", "نموذج لغوي", "برنامج ذكاء", "لغة نموذج", "openai"]
    t = text or ""
    for w in forbidden_words:
        t = t.replace(w, "")
    return t.strip()

# ---------------------------
# استدعاء API تاعك
# ---------------------------
def call_baithek_api(ctx, lang="ar"):
    payload = {"name": "Usama", "lang": lang, "messages": ctx, "n": 1, "stream": False}

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://baithek.com",
        "Referer": "https://baithek.com/",
    }

    res = session.post(API_URL, json=payload, headers=headers, timeout=(15, 60))
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
# ✅ Weather (Open-Meteo) + ✅ Prayer (AlAdhan)
# ---------------------------
def weather_5days(city: str) -> str:
    # Geocoding
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=15
    ).json()

    if not geo.get("results"):
        return "ما لقيتش هاد البلاصة 😅 جرب اسم آخر (مثال: Alger, Oran, Setif) 🌦️"

    r0 = geo["results"][0]
    lat, lon = r0["latitude"], r0["longitude"]
    place = f'{r0.get("name","")}, {r0.get("country","")}'

    fc = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max",
            "forecast_days": 5,
            "timezone": "auto"
        },
        timeout=20
    ).json()

    d = fc.get("daily", {})
    dates = d.get("time", [])
    tmax = d.get("temperature_2m_max", [])
    tmin = d.get("temperature_2m_min", [])
    pop = d.get("precipitation_probability_max", [])
    wind = d.get("windspeed_10m_max", [])

    lines = [f"🌦️ طقس 5 أيام لـ {place}:"]
    for i in range(min(5, len(dates))):
        rain_emoji = "🌧️" if (pop[i] if i < len(pop) else 0) >= 40 else "☁️"
        lines.append(
            f"- {dates[i]}: {rain_emoji} {tmin[i]}° / {tmax[i]}° | 💨 {wind[i]} km/h | 🌧️ {pop[i]}%"
        )
    return "\n".join(lines)

def prayer_times(city: str, country="Algeria") -> str:
    # AlAdhan by city
    data = requests.get(
        "https://api.aladhan.com/v1/timingsByCity",
        params={"city": city, "country": country, "method": 3},
        timeout=20
    ).json()

    if data.get("code") != 200:
        return "ما قدرتش نجيب أوقات الصلاة 😅 جرب اسم الولاية بالإنجليزية (Algiers / Oran / Annaba) 🕌"

    t = data["data"]["timings"]
    return (
        f"🕌 أوقات الصلاة في {city}:\n"
        f"🌙 Fajr: {t.get('Fajr')}\n"
        f"☀️ Dhuhr: {t.get('Dhuhr')}\n"
        f"🏞️ Asr: {t.get('Asr')}\n"
        f"🌇 Maghrib: {t.get('Maghrib')}\n"
        f"🌃 Isha: {t.get('Isha')}\n"
        f"\nإذا حبيت ولاية أخرى قولّي اسمها 😉"
    )

def about_text():
    return (
        "ℹ️ Botivity 🔥\n"
        "بوت مسنجر خفيف وذكي، يجاوبك و يعاونك في أي حاجة: دراسة، نصائح، أفكار، وحتّى خدمات كيما الطقس والصلاة 😎\n\n"
        "✨ Smarter Conversations Start Here\n"
        "👨‍💻 By FaresCodeX 🇩🇿🔥"
    )

# ---------------------------
# الذكاء (الرد العام)
# ---------------------------
def get_ai_response(user_id, message_text):
    if user_id not in user_memory:
        user_memory[user_id] = []

    system_prompt = (
        "انت شاب جزائري دزيري 100%.\n"
        "تهدر كيما صاحب في قهوة، طبيعي ومرح.\n"
        "انت مساعد شامل تعاون في أي موضوع.\n"
        "ردودك تكون على قد السؤال: القصير قصير، واللي يحتاج شرح تنظمو بنقاط.\n"
        "استعمل ايموجيات بذكاء حسب السياق (ماشي بزاف).\n"
        "إذا السؤال غامض اسقسي توضيح.\n"
        "مهم: ما تقولش بلي انت AI ولا روبوت ولا تذكر ذكاء اصطناعي.\n"
        "غير إذا تسقساوك شكون طورك قول: \"طورني فارس 🇩🇿 شاب جزائري خطير ونفتخر بيه 🔥\" وما تزيد حتى حاجة."
    )

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
            return reply or "سمحلي ما فهمتش مليح 😅"
        except Exception as e:
            print("API error:", repr(e))
            time.sleep(0.7)

    return "راه صرا مشكل في الاتصال 😅"

# ---------------------------
# ✅ معالجة الأزرار (postbacks) + الأوامر
# ---------------------------
def handle_postback(sender_id, payload):
    if payload == "GET_STARTED":
        send_quick_replies(
            sender_id,
            "أهلا بيك في Botivity 😎🔥 واش تحب دير؟",
            [
                {"title": "🌦️ الطقس", "payload": "CMD_WEATHER"},
                {"title": "🕌 الصلاة", "payload": "CMD_PRAYER"},
                {"title": "ℹ️ About", "payload": "CMD_ABOUT"},
            ]
        )
        return

    if payload == "CMD_ABOUT":
        send_message(sender_id, about_text())
        return

    if payload == "CMD_WEATHER":
        user_state[sender_id] = {"mode": "weather_wait_city"}
        send_message(sender_id, "🌦️ عطيني اسم المدينة/الولاية (عربي ولا إنجليزي)… مثال: Alger / Oran / Setif 😄")
        return

    if payload == "CMD_PRAYER":
        user_state[sender_id] = {"mode": "prayer_wait_city"}
        send_message(sender_id, "🕌 عطيني اسم الولاية بالإنجليزية باش يجيبها صح (مثال: Algiers / Oran / Annaba) 😉")
        return

def handle_message(sender_id, message_text):
    try:
        if not message_text:
            send_message(sender_id, "بعتلي كتابة برك باش نجاوبك 😄✍️")
            return

        txt = message_text.strip()

        # سؤال المطور
        if "شكون طورك" in txt:
            send_message(sender_id, "طورني فارس 🇩🇿 شاب جزائري خطير و نفتخر بيه 🔥")
            return

        # إذا راه مستني مدينة للطقس/الصلاة
        mode = (user_state.get(sender_id) or {}).get("mode")

        if mode == "weather_wait_city":
            user_state.pop(sender_id, None)
            send_typing(sender_id, "typing_on")
            reply = weather_5days(txt)
            send_typing(sender_id, "typing_off")
            send_message(sender_id, reply)
            return

        if mode == "prayer_wait_city":
            user_state.pop(sender_id, None)
            send_typing(sender_id, "typing_on")
            reply = prayer_times(txt)
            send_typing(sender_id, "typing_off")
            send_message(sender_id, reply)
            return

        # أوامر نصية سريعة حتى بلا أزرار
        low = txt.lower()
        if low in ["طقس", "weather", "meteo"]:
            handle_postback(sender_id, "CMD_WEATHER")
            return
        if low in ["صلاة", "اوقات الصلاة", "prayer", "adhan", "اذان"]:
            handle_postback(sender_id, "CMD_PRAYER")
            return
        if low in ["about", "من انت", "من تكون", "تعريف"]:
            handle_postback(sender_id, "CMD_ABOUT")
            return

        # الرد العام بالذكاء
        send_typing(sender_id, "typing_on")
        reply = get_ai_response(sender_id, txt)
        send_typing(sender_id, "typing_off")
        send_message(sender_id, reply)

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

            # ✅ postback (زر menu / get started)
            if "postback" in messaging:
                payload = (messaging.get("postback") or {}).get("payload")
                if payload:
                    threading.Thread(target=handle_postback, args=(sender_id, payload), daemon=True).start()
                continue

            # ✅ quick reply payload
            msg_obj = messaging.get("message") or {}
            if msg_obj.get("quick_reply"):
                payload = msg_obj["quick_reply"].get("payload")
                if payload:
                    threading.Thread(target=handle_postback, args=(sender_id, payload), daemon=True).start()
                continue

            # ✅ text message
            message_text = (msg_obj.get("text") or "").strip()
            threading.Thread(target=handle_message, args=(sender_id, message_text), daemon=True).start()

    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
