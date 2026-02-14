import os
import time
import re
import requests
from flask import Flask, request
from bs4 import BeautifulSoup
from Crypto.Cipher import AES

app = Flask(__name__)

# ENV variables
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "PUT_YOUR_PAGE_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "faresdz123")
API_URL = os.getenv("API_URL", "https://asmodeus.free.nf/index.php")

# Memory
user_memory = {}

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


# ✅ Route test باش تتأكد Render يخدم
@app.route("/test", methods=["GET"])
def test():
    return "السيرفر راه يخدم 😎🔥", 200


# Solve cookie challenge
def solve_cookie_challenge():
    try:
        r = session.get(API_URL, timeout=30)
        matches = re.findall(r'toNumbers\("([a-f0-9]+)"\)', r.text)

        if len(matches) >= 3:
            a = bytes.fromhex(matches[0])
            b = bytes.fromhex(matches[1])
            c = bytes.fromhex(matches[2])

            cipher = AES.new(a, AES.MODE_CBC, b)
            cookie_val = cipher.decrypt(c).hex()

            session.cookies.set("__test", cookie_val, domain="asmodeus.free.nf", path="/")
            session.get(API_URL + "?i=1", timeout=30)
    except:
        pass


# typing indicator
def send_typing(recipient_id, action="typing_on"):
    try:
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        data = {"recipient": {"id": recipient_id}, "sender_action": action}
        requests.post(url, json=data, timeout=10)
    except:
        pass


# send message
def send_message(recipient_id, text):
    try:
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
        requests.post(url, json=data, timeout=10)
    except:
        pass


# clean reply
def clean_reply(text: str) -> str:
    forbidden_words = ["AI", "ذكاء اصطناعي", "روبوت", "نموذج لغوي", "برنامج ذكاء", "لغة نموذج"]
    for word in forbidden_words:
        text = text.replace(word, "")
    return text.strip()


def get_ai_response(user_id, message_text):
    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append("User: " + message_text)
    user_memory[user_id] = user_memory[user_id][-20:]

    history = "\n".join(user_memory[user_id][-10:])

    system_prompt = """
انت شاب جزائري ذكي بزاف.
تهدر غير بالدزيرية الشبابية الطبيعية.
ما تقولش نهائيًا بلي انت AI ولا روبوت ولا برنامج.
ما تذكرش كلمة ذكاء اصطناعي.

جاوب:
- منظم
- شرح واضح
- نقاط إذا لزم
- ايموجيات خفيفة 😎🔥
- طبيعي بزاف كيما إنسان

ما تذكرش المطور من روحك.
غير إذا تسقساوك شكون طورك قول:
"طورني فارس 🇩🇿 شاب جزائري خطير و نفتخر بيه 🔥"
و ما تزيد حتى حاجة أخرى.
"""

    full_prompt = f"{system_prompt}\n\nالمحادثة:\n{history}\n\nجاوب على آخر رسالة فقط:"

    payload = {"model": "V3.2", "msg": full_prompt}

    for _ in range(2):
        try:
            solve_cookie_challenge()

            response = session.post(API_URL, data=payload, timeout=60)
            soup = BeautifulSoup(response.text, "html.parser")
            pre = soup.find("pre")

            if pre:
                reply = clean_reply(pre.get_text().strip())
                user_memory[user_id].append("Bot: " + reply)
                user_memory[user_id] = user_memory[user_id][-20:]
                return reply if reply else "سمحلي خويا ما فهمتش مليح 😅"

            return "سمحلي خويا صرا مشكل 😅"
        except:
            time.sleep(1)

    return "راه صرا مشكل في الاتصال 😅"


# Verify webhook (GET)
@app.route("/", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN and challenge:
        return challenge

    return "Error", 403


# Receive messages (POST)
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

            if not message_text:
                send_message(sender_id, "بعتلي كتابه برك باش نجاوبك 😄✍️")
                continue

            if "شكون طورك" in message_text:
                send_message(sender_id, "طورني فارس 🇩🇿 شاب جزائري خطير و نفتخر بيه 🔥")
                continue

            send_typing(sender_id, "typing_on")
            time.sleep(1.5)

            reply = get_ai_response(sender_id, message_text)

            send_typing(sender_id, "typing_off")
            send_message(sender_id, reply)

    return "OK", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)