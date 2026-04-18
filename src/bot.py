import requests
from config import BOT_TOKEN
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

client = MongoClient("mongodb://localhost:27017/")
db = client["telegram_bot"]
messages_col = db["messages"]

def save_message(message):
    messages_col.insert_one({
        "chat_id": message["chat"]["id"],
        "user_id": message["from"]["id"],
        "text": message.get("text", ""),
        "timestamp": datetime.now(timezone.utc)
    })

def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)


def get_last_hour_messages(chat_id):
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    cursor = messages_col.find({
        "chat_id": chat_id,
        "timestamp": {"$gte": one_hour_ago}
    }).sort("timestamp", 1)

    return list(cursor)

def handle_message(message):
    save_message(message)

    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    text_lower = text.lower()

    # TODO Agent stuff
    if text_lower.contains() == "hi":
        send_message(chat_id, "👋 Hello!")
    elif text_lower == "/help":
        send_message(chat_id, "Commands: hi, /help")
    else:
        send_message(chat_id, f"You said: {text}")
