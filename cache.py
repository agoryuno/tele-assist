from datetime import datetime

import redis
from utils import get_config

config = get_config()

HOST = config["CACHE"]["HOST"]
PASSWORD = config["CACHE"]["PASSWORD"]
PORT = config["CACHE"]["PORT"]


def get_redis_client(host=HOST, port=PORT, password=PASSWORD):
    # Connect to the local Redis instance
    redis_client = redis.StrictRedis(host='localhost', 
                                     port=6379, 
                                     db=0,
                                     password=password)

    # Test the connection
    try:
        redis_client.ping()
        print("Connected to Redis!")
    except redis.ConnectionError:
        print("Failed to connect to Redis.")
    return redis_client


def _record(client, chat_id, msg_id, _type, value):
    client.set(f"chat_id:<{chat_id}>:msg_id:<{msg_id}>:{_type}", value)


def save_message(client, chat_id, message_id, message_text):
    # Add the message to the cache
    _record(client, chat_id, message_id, "text", message_text)
    _record(client, chat_id, message_id, "time", datetime.now().timestamp())


def update_message(client, chat_id, message_id, message_text):
    # Update the message in the cache
    _record(client, chat_id, message_id, "text", message_text)