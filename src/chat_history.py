import logging
import os
from datetime import datetime, timezone

from pymongo import MongoClient


DEFAULT_MONGODB_URI = "mongodb://localhost:27017"
DEFAULT_MONGODB_DB = "telegram_bot"

logger = logging.getLogger(__name__)


def get_display_name(user: dict | None) -> str | None:
    if not user:
        return None

    username = user.get("username")
    if username:
        return username

    full_name = " ".join(part for part in [user.get("first_name"), user.get("last_name")] if part)
    return full_name or None


def replace_utf16_span(text: str, offset: int, length: int, replacement: str) -> str:
    encoded = text.encode("utf-16-le")
    start = offset * 2
    end = (offset + length) * 2
    return encoded[:start].decode("utf-16-le") + replacement + encoded[end:].decode("utf-16-le")


def normalize_mentions(text: str, entities: list[dict] | None) -> str:
    normalized = text
    for entity in sorted(entities or [], key=lambda item: item.get("offset", 0), reverse=True):
        if entity.get("type") != "text_mention":
            continue

        replacement = get_display_name(entity.get("user")) or "unknown"
        normalized = replace_utf16_span(
            normalized,
            int(entity.get("offset", 0)),
            int(entity.get("length", 0)),
            replacement,
        )

    return normalized


class DataBase:
    def __init__(self, uri: str | None = None, db_name: str | None = None):
        self.client = MongoClient(
            uri or os.getenv("MONGODB_URI", DEFAULT_MONGODB_URI),
            serverSelectionTimeoutMS=3000,
        )
        self.db = self.client[db_name or os.getenv("MONGODB_DB", DEFAULT_MONGODB_DB)]
        self.messages_col = self.db["messages"]
        logger.info("chat history db initialized db=%s", self.db.name)

    def save_message(self, message):
        doc = {
            "chat_id": message["chat"]["id"],
            "message_id": message.get("message_id"),
            "user_id": message["from"]["id"],
            "from_bot": False,
            "username": message["from"].get("username"),
            "first_name": message["from"].get("first_name"),
            "last_name": message["from"].get("last_name"),
            "timestamp": datetime.now(timezone.utc),
        }

        if "reply_to_message" in message:
            doc["reply_to_message"] = message.get("reply_to_message")

        # text message
        if "text" in message:
            doc["type"] = "text"
            doc["text"] = normalize_mentions(message["text"], message.get("entities"))

        # TODO what if more photos?
        elif "photo" in message:
            doc["type"] = "photo"

            # Telegram sends multiple sizes → last one is highest quality
            photo = message["photo"][-1]

            doc["file_id"] = photo["file_id"]
            doc["caption"] = normalize_mentions(message.get("caption", ""), message.get("caption_entities"))

        self.messages_col.insert_one(doc)
        logger.info(
            "saved message chat_id=%s message_id=%s user_id=%s type=%s",
            doc["chat_id"],
            doc.get("message_id"),
            doc["user_id"],
            doc.get("type"),
        )

    def save_bot_message(self, message):
        doc = {
            "chat_id": message["chat"]["id"],
            "message_id": message.get("message_id"),
            "user_id": message.get("from", {}).get("id"),
            "from_bot": True,
            "username": message.get("from", {}).get("username"),
            "first_name": message.get("from", {}).get("first_name"),
            "last_name": message.get("from", {}).get("last_name"),
            "timestamp": datetime.now(timezone.utc),
            "type": "text",
            "text": message.get("text", ""),
        }
        self.messages_col.insert_one(doc)
        logger.info(
            "saved bot message chat_id=%s message_id=%s text=%r",
            doc["chat_id"],
            doc.get("message_id"),
            doc.get("text"),
        )


    def get_recent_messages(self, chat_id, limit=50):
        cursor = (
            self.messages_col.find({"chat_id": chat_id})
            .sort("timestamp", -1)
            .limit(limit)
        )

        messages = list(reversed(list(cursor)))
        logger.info(
            "loaded recent messages chat_id=%s limit=%s count=%s",
            chat_id,
            limit,
            len(messages),
        )
        return messages

    def find_one(self, pred):
        logger.debug("find_one in chat history with pred=%s", pred)
        return self.messages_col.find_one(pred)
