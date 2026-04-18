from datetime import datetime, timezone

from pymongo import MongoClient


class DataBase:
    client = MongoClient("mongodb://localhost:27017/")
    db = client["telegram_bot"]
    messages_col = db["messages"]

    def save_message(self, message):
        doc = {
            "chat_id": message["chat"]["id"],
            "user_id": message["from"]["id"],
            "from_bot": False,
            "username": message["from"].get("username"),
            "timestamp": datetime.now(timezone.utc),
        }

        # text message
        if "text" in message:
            doc["type"] = "text"
            doc["text"] = message["text"]

        # TODO what if more photos?
        elif "photo" in message:
            doc["type"] = "photo"

            # Telegram sends multiple sizes → last one is highest quality
            photo = message["photo"][-1]

            doc["file_id"] = photo["file_id"]
            doc["caption"] = message.get("caption", "")

        self.messages_col.insert_one(doc)


    def get_recent_messages(self, chat_id, limit=50):
        cursor = (
            self.messages_col.find({"chat_id": chat_id})
            .sort("timestamp", -1)
            .limit(limit)
        )

        return list(reversed(list(cursor)))
    
    def find_one(self,  pred):
        return self.messages_col.find_one(pred)
