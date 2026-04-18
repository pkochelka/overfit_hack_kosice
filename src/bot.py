import requests
from config import BOT_TOKEN
from baml_client.types import Message, Debt
from chat_history import DataBase

BOT_USERNAME = "hack_kosice_bot"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

db = DataBase()

def load_photo_message(msg):
    pass

def load_text_message(msg):
    return Message(msg.get("username"), msg.get("text"))

def get_chat_history(chat_id):
    output = []
    for msg in db.get_recent_messages(chat_id):
        if msg.get("type") == "text":
            output.append(load_text_message(msg))


def handle_message(message):
    db.save_message(message)
    text = message.get("text", "")

    # If was not tagged, stop
    if f"@{BOT_USERNAME.lower()}" not in text.lower():
        return

    # Otherwise recap history
    chat_id = message["chat"]["id"]
    return get_chat_history(chat_id)

    #TODO remove all database entries?

    
def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)
