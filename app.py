import os
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "faresdz123")
API_URL = os.getenv("API_URL", "https://baithek.com/chatbee/health_ai/ai_vision.php")

user_memory = {}
user_state = {}  # {user_id: {"mode":"weather_wait_wilaya"} ...}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
})

# ---------------------------
# 58 ولاية (عربي/إنجليزي) + مدينة مرجعية للصلاة
# ملاحظة: للطقس والصلاة نحتاج "مدينة" معروفة في API
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

# نبني قاموسات بحث سريع
W_BY_AR = {a: {"ar": a, "en": e, "city": c} for a, e, c in WILAYAS}
W_BY_EN = {e.lower(): {"ar": a, "en": e, "city": c} for a, e, c in WILAYAS}

def normalize_name(s: str) -> str:
    s = (s or "").strip()
    # تنظيف بسيط
    s = s.replace("ولاية", "").strip()
    return s

def resolve_wilaya(user_text: str):
    """
    يرجّع dict فيها: ar/en/city
    يقبل عربي أو إنجليزي
    """
    name = normalize_name(user_text)
    if not name:
        return None

    # عربي مباشر
    if name in W_BY_AR:
        return W_BY_AR[name]

    # إنجليزي (lower)
    low = name.lower()
    if low in W_BY_EN:
        return W_BY_EN[low]

    # محاولات بسيطة (بدون تعقيد)
    # مثال: "Alger" => نربطها بـ Algiers
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
    payload = {"recipient": {"id": recipient_id}, "sender_action": action}
    fb_post("/me/messages", payload, timeout=10)

def send_message(recipient_id, text):
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    fb_post("/me/messages", payload, timeout=20)

def send_quick_replies(recipient_id, text, replies):
    """
    quick replies يبانوا تحت الرسالة بصح يروحو كي تختار واحد
    replies = [{"title":"🌦️ الطقس","payload":"CMD_WEATHER"}, ...]
    """
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
# ✅ Setup (Get Started + Ice Breakers + Persistent Menu)
# ---------------------------
def setup_messenger_profile():
    profile_payload = {
        "get_started": {"payload": "GET_STARTED"},

        # ✅ Ice Breakers (يبانو في بداية الشات كيما صورتك)
        "ice_breakers": [
            {"question": "🌦️ الطقس", "payload": "CMD_WEATHER"},
            {"question": "🕌 أوقات الصلاة", "payload": "CMD_PRAYER"},
            {"question": "ℹ️ About Botivity", "payload": "CMD_ABOUT"},
        ],

        # ✅ Persistent Menu (ثابت في ☰)
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
# ✅ Weather + ✅ Prayer
# ---------------------------
AR_DAYS = ["الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]

def day_name_from_date(date_str: str) -> str:
    # date_str = "YYYY-MM-DD"
    try:
        y, m, d = date_str.split("-")
        import datetime
        dt = datetime.date(int(y), int(m), int(d))
        # Monday=0
        return AR_DAYS[dt.weekday()]
    except:
        return date_str

def weather_5days(wilaya_input: str) -> str:
    w = resolve_wilaya(wilaya_input)
    if not w:
        return "🌦️ عطيني اسم الولاية صح (عربي ولا إنجليزي).\nمثال: الجزائر / Algiers — وهران / Oran 😄"

    # Open-Meteo geocoding (نستعمل الاسم بالإنجليزية باش يلقاه)
    city = w["city"]
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=12
    ).json()

    if not geo.get("results"):
        return f"ما لقيتش إحداثيات {w['ar']} 😅 جرب تكتبها بالإنجليزية: {w['en']}"

    r0 = geo["results"][0]
    lat, lon = r0["latitude"], r0["longitude"]

    fc = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max",
            "forecast_days": 5,
            "timezone": "auto"
        },
        timeout=15
    ).json()

    d = fc.get("daily", {})
    dates = d.get("time", [])
    tmax = d.get("temperature_2m_max", [])
    tmin = d.get("temperature_2m_min", [])
    pop = d.get("precipitation_probability_max", [])
    wind = d.get("windspeed_10m_max", [])

    lines = [f"🌦️ طقس 5 أيام — {w['ar']} ({w['en']}):"]
    for i in range(min(5, len(dates))):
        p = pop[i] if i < len(pop) else 0
        wv = wind[i] if i < len(wind) else 0
        mn = tmin[i] if i < len(tmin) else "-"
        mx = tmax[i] if i < len(tmax) else "-"

        if p >= 70:
            emoji = "⛈️"
        elif p >= 40:
            emoji = "🌧️"
        elif p >= 20:
            emoji = "🌦️"
        else:
            emoji = "☀️"

        day_ar = day_name_from_date(dates[i])
        lines.append(f"- {day_ar}: {emoji} {mn}° / {mx}° | 💨 {wv} كم/س | 🌧️ {p}%")

    lines.append("\nإذا تحب ولاية أخرى قولّي اسمها 😉")
    return "\n".join(lines)

def prayer_times(wilaya_input: str) -> str:
    w = resolve_wilaya(wilaya_input)
    if not w:
        return "🕌 عطيني اسم الولاية صح (عربي ولا إنجليزي).\nمثال: قسنطينة / Constantine 😄"

    city = w["city"]
    # AlAdhan by city
    data = requests.get(
        "https://api.aladhan.com/v1/timingsByCity",
        params={"city": city, "country": "Algeria", "method": 3},
        timeout=15
    ).json()

    if data.get("code") != 200:
        return f"ما قدرتش نجيب أوقات الصلاة لـ {w['ar']} 😅 جرّب تكتبها بالإنجليزية: {w['en']}"

    t = data["data"]["timings"]
    return (
        f"🕌 أوقات الصلاة — {w['ar']} ({w['en']}):\n"
        f"🌙 الفجر: {t.get('Fajr')}\n"
        f"☀️ الظهر: {t.get('Dhuhr')}\n"
        f"🏞️ العصر: {t.get('Asr')}\n"
        f"🌇 المغرب: {t.get('Maghrib')}\n"
        f"🌃 العشاء: {t.get('Isha')}\n"
        f"\nإذا تحب ولاية أخرى قولّي اسمها 😉"
    )

def about_text():
    return (
        "ℹ️ Botivity 🔥\n"
        "مساعد مسنجر جزائري خفيف ومليح 😎\n"
        "يساعدك في أي حاجة: دراسة، أفكار، نصائح، وحتى خدمات كيما الطقس 🌦️ و أوقات الصلاة 🕌.\n\n"
        "✨ Smarter Conversations Start Here\n"
        "👨‍💻 By FaresCodeX 🇩🇿🔥"
    )

# ---------------------------
# الرد العام
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
            time.sleep(0.5)

    return "راه صرا مشكل في الاتصال 😅"

# ---------------------------
# ✅ معالجة الأزرار (postbacks) + الأوامر
# ---------------------------
def show_main_options(sender_id, text="وش تحب دير؟ 😄"):
    # هذي Quick Replies (يروحو كي تختار) بصح يعاونو بزاف
    send_quick_replies(
        sender_id,
        text,
        [
            {"title": "🌦️ الطقس", "payload": "CMD_WEATHER"},
            {"title": "🕌 الصلاة", "payload": "CMD_PRAYER"},
            {"title": "ℹ️ About", "payload": "CMD_ABOUT"},
        ]
    )

def handle_postback(sender_id, payload):
    if payload == "GET_STARTED":
        show_main_options(sender_id, "أهلا بيك في Botivity 😎🔥")
        return

    if payload == "CMD_ABOUT":
        send_message(sender_id, about_text())
        return

    if payload == "CMD_WEATHER":
        user_state[sender_id] = {"mode": "weather_wait_wilaya"}
        send_message(sender_id, "🌦️ عطيني اسم الولاية (عربي ولا إنجليزي)… مثال: الجزائر / Algiers 😄")
        return

    if payload == "CMD_PRAYER":
        user_state[sender_id] = {"mode": "prayer_wait_wilaya"}
        send_message(sender_id, "🕌 عطيني اسم الولاية (عربي ولا إنجليزي)… مثال: وهران / Oran 😉")
        return

def handle_message(sender_id, message_text):
    try:
        if not message_text:
            send_message(sender_id, "بعتلي كتابة برك باش نجاوبك 😄✍️")
            return

        txt = message_text.strip()

        if "شكون طورك" in txt:
            send_message(sender_id, "طورني فارس 🇩🇿 شاب جزائري خطير و نفتخر بيه 🔥")
            return

        # إذا راه مستني ولاية للطقس/الصلاة
        mode = (user_state.get(sender_id) or {}).get("mode")

        if mode == "weather_wait_wilaya":
            user_state.pop(sender_id, None)
            send_typing(sender_id, "typing_on")
            reply = weather_5days(txt)
            send_typing(sender_id, "typing_off")
            send_message(sender_id, reply)
            show_main_options(sender_id, "تحب تدير حاجة أخرى؟ 😉")
            return

        if mode == "prayer_wait_wilaya":
            user_state.pop(sender_id, None)
            send_typing(sender_id, "typing_on")
            reply = prayer_times(txt)
            send_typing(sender_id, "typing_off")
            send_message(sender_id, reply)
            show_main_options(sender_id, "نزيد نعاونك فحاجة أخرى؟ 😄")
            return

        # أوامر نصية سريعة
        low = txt.lower()
        if low in ["طقس", "weather", "meteo", "مناخ"]:
            handle_postback(sender_id, "CMD_WEATHER")
            return
        if low in ["صلاة", "اوقات الصلاة", "أوقات الصلاة", "prayer", "adhan", "اذان", "آذان"]:
            handle_postback(sender_id, "CMD_PRAYER")
            return
        if low in ["about", "من انت", "من تكون", "تعريف", "شنو هو botivity", "botivity"]:
            handle_postback(sender_id, "CMD_ABOUT")
            return

        # الرد العام
        send_typing(sender_id, "typing_on")
        reply = get_ai_response(sender_id, txt)
        send_typing(sender_id, "typing_off")
        send_message(sender_id, reply)

        # اختياري: خليه دايمًا يعاود يبين اختيارات
        show_main_options(sender_id, "حاب تزيد؟ 😄")

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

            # postback (menu / get started)
            if "postback" in messaging:
                payload = (messaging.get("postback") or {}).get("payload")
                if payload:
                    threading.Thread(target=handle_postback, args=(sender_id, payload), daemon=True).start()
                continue

            # quick reply payload
            msg_obj = messaging.get("message") or {}
            if msg_obj.get("quick_reply"):
                payload = msg_obj["quick_reply"].get("payload")
                if payload:
                    threading.Thread(target=handle_postback, args=(sender_id, payload), daemon=True).start()
                continue

            # text message
            message_text = (msg_obj.get("text") or "").strip()
            threading.Thread(target=handle_message, args=(sender_id, message_text), daemon=True).start()

    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
