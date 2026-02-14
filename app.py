import os
import time
import threading
import requests
from flask import Flask, request

app = Flask(__name__)

# ENV variables (لازم تديرهم في Render)
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "faresdz123")
API_URL = os.getenv("API_URL", "https://baithek.com/chatbee/health_ai/ai_vision.php")

# Memory (خفيفة)
user_memory = {}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
})


@app.route("/test", methods=["GET"])
def test():
    return "السيرفر راه يخدم 😎🔥", 200


def send_typing(recipient_id, action="typing_on"):
    if not PAGE_ACCESS_TOKEN:
        return
    try:
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        data = {"recipient": {"id": recipient_id}, "sender_action": action}
        requests.post(url, json=data, timeout=10)
    except:
        pass


def send_message(recipient_id, text):
    if not PAGE_ACCESS_TOKEN:
        return
    try:
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
        requests.post(url, json=data, timeout=15)
    except:
        pass


def clean_reply(text: str) -> str:
    forbidden_words = ["AI", "ذكاء اصطناعي", "روبوت", "نموذج لغوي", "برنامج ذكاء", "لغة نموذج", "openai"]
    t = text or ""
    for w in forbidden_words:
        t = t.replace(w, "")
    return t.strip()


def call_baithek_api(ctx, lang="ar"):
    """
    يبعث نفس payload بصح stream=False باش ما يطيحش الاتصال
    """
    payload = {
        "name": "Usama",
        "lang": lang,
        "messages": ctx,
        "n": 1,
        "stream": False  # ✅ بدلناها
    }

    # ✅ Headers كيما المتصفح (باش ما يديرش reset)
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://baithek.com",
        "Referer": "https://baithek.com/",
    }

    res = session.post(
        API_URL,
        json=payload,
        headers=headers,
        timeout=(15, 60)  # ✅ زيدنا شوية
    )

    # ✅ Debug في logs باش نعرفو السبب الحقيقي
    print("API STATUS:", res.status_code)
    print("API HEADERS:", dict(res.headers))
    print("API TEXT:", (res.text or "")[:2000])

    res.raise_for_status()

    data = res.json()

    result = (
        (data.get("choices") or [{}])[0].get("message", {}).get("content")
        or data.get("answer")
        or data.get("reply")
        or data.get("message")
        or data.get("result")
    )

    if not result:
        raise ValueError("No reply in API response")

    return clean_reply(result)


def get_ai_response(user_id, message_text):
    if user_id not in user_memory:
        user_memory[user_id] = []

    system_prompt = (
        "انت شاب جزائري ذكي بزاف.\n"
        "تهدر غير بالدزيرية الشبابية الطبيعية.\n"
        "ما تقولش نهائيًا بلي انت AI ولا روبوت ولا برنامج.\n"
        "ما تذكرش كلمة ذكاء اصطناعي.\n\n"
        "جاوب:\n"
        "- منظم\n"
        "- شرح واضح\n"
        "- نقاط إذا لزم\n"
        "- ايموجيات خفيفة 😎🔥\n"
        "- طبيعي بزاف كيما إنسان\n\n"
        "ما تذكرش المطور من روحك.\n"
        "غير إذا تسقساوك شكون طورك قول:\n"
        "\"طورني فارس 🇩🇿 شاب جزائري خطير و نفتخر بيه 🔥\"\n"
        "و ما تزيد حتى حاجة أخرى."
    )

    hist = user_memory[user_id][-8:]
    ctx = [{"role": "system", "content": system_prompt}]
    for h in hist:
        ctx.append(h)
    ctx.append({"role": "user", "content": message_text})

    for _ in range(2):
        try:
            reply = call_baithek_api(ctx, lang="ar")
            user_memory[user_id].append({"role": "user", "content": message_text})
            user_memory[user_id].append({"role": "assistant", "content": reply})
            user_memory[user_id] = user_memory[user_id][-16:]
            return reply if reply else "سمحلي خويا ما فهمتش مليح 😅"
        except Exception as e:
            print("API error:", repr(e))  # ✅ بدلناها
            time.sleep(0.7)

    return "راه صرا مشكل في الاتصال 😅"


@app.route("/", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN and challenge:
        return challenge, 200
    return "Error", 403


def handle_message(sender_id, message_text):
    try:
        if not message_text:
            send_message(sender_id, "بعتلي كتابه برك باش نجاوبك 😄✍️")
            return

        if "شكون طورك" in message_text:
            send_message(sender_id, "طورني فارس 🇩🇿 شاب جزائري خطير و نفتخر بيه 🔥")
            return

        send_typing(sender_id, "typing_on")
        reply = get_ai_response(sender_id, message_text)
        send_typing(sender_id, "typing_off")
        send_message(sender_id, reply)
    except Exception as e:
        print("handle_message error:", repr(e))


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

            msg_obj = messaging.get("message") or {}
            message_text = (msg_obj.get("text") or "").strip()

            threading.Thread(
                target=handle_message,
                args=(sender_id, message_text),
                daemon=True
            ).start()

    return "OK", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
