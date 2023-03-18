from typing import List, Union
from uuid import uuid4
from datetime import datetime

import numpy as np

import redis
from redis.commands.search.indexDefinition import (
    IndexDefinition,
    IndexType
)
from redis.commands.search.query import Query, NumericFilter
from redis.commands.search.field import (
    TextField,
    VectorField,
    NumericField
)

from utils import get_config
from _openai import embed_text


config = get_config()

HOST = config["CACHE"]["HOST"]
PASSWORD = config["CACHE"]["PASSWORD"]
PORT = config["CACHE"]["PORT"]
DISTANCE_METRIC = config["CACHE"]["DISTANCE_METRIC"]
EMBEDDING_DIM = config["CACHE"]["EMBEDDING_DIM"]
INDEX_NAME = config["CACHE"]["INDEX_NAME"]
PREFIX = "message"


def create_index(
        client: redis.Redis,
        index_name=INDEX_NAME, 
        embedding_dim=EMBEDDING_DIM, 
        distance_metric=DISTANCE_METRIC,
        prefix=PREFIX):
    try:
        client.ft(INDEX_NAME).info()
        return
    except:
        pass
    
    user_id = NumericField(name="user_id")
    message_id = NumericField(name="message_id")
    message = TextField(name="message")
    message_embedding = VectorField("message_embedding",
                                    "FLAT", {
                                        "TYPE": "FLOAT32",
                                        "DIM":  embedding_dim,
                                        "DISTANCE_METRIC": distance_metric,
                                        "INITIAL_CAP": 1000,
                                    }
    )
    timestamp = NumericField(name="timestamp")

    fields = [user_id, message_id, message, message_embedding, timestamp]

    client.ft(index_name).create_index(
                        fields = fields,
                        definition = IndexDefinition(
                                            prefix=[prefix], 
                                            index_type=IndexType.HASH)
    )


def search_redis(
    client: redis.Redis,
    user_id: Union[int, str],
    embedded_query: List,
    index_name: str = INDEX_NAME,
    vector_field: str = "message_embedding",
    return_fields: list = ["message", "message_id", "user_id", "vector_score", "timestamp"],
    hybrid_fields = "*",
    k: int = 20,
    ) -> List[dict]:

    # Creates embedding vector from user query
    #embedded_query = embed_text(user_query)

    user_id = int(user_id)
    # Prepare the Query
    base_query = f'{hybrid_fields}=>[KNN {k} @{vector_field} $vector AS vector_score]'
    query = (
        Query(base_query)
         .add_filter(NumericFilter("user_id", user_id, user_id))
         .return_fields(*return_fields)
         .sort_by("vector_score")
         .paging(0, k)
         .dialect(2)
    )
    params_dict = {"vector": np.array(embedded_query).astype(dtype=np.float32).tobytes()}

    # perform vector search
    results = client.ft(index_name).search(query, params_dict)
    return results.docs


def get_redis_client(host=HOST, port=PORT, password=PASSWORD):
    # Connect to the local Redis instance
    redis_client = redis.StrictRedis(host=host, 
                                     port=port, 
                                     db=0,
                                     password=password)

    # Test the connection
    try:
        redis_client.ping()
        print("Connected to Redis!")
    except redis.ConnectionError:
        print("Failed to connect to Redis.")
    return redis_client


def _record_embedding(client: redis.Redis, 
                      user_id, 
                      message, 
                      message_embedding,
                      prefix=PREFIX):
    message_embedding = np.array(message_embedding, dtype=np.float32).tobytes()
    timestamp = datetime.now().timestamp()
    msg_hash = uuid4().hex
    key = f"{prefix}:<{user_id}><{msg_hash}>"
    timestamp = datetime.now().timestamp()
    mapping = {"user_id": int(user_id),
               #"message_id": int(msg_id),
               "message": message, 
               "message_embedding": message_embedding,
               "timestamp": float(timestamp),}
    client.hset(key, mapping = mapping)
    return key, msg_hash



def _update_message_id(client, 
                       key,
                       user_id,
                       message_id,  
                       ):
    # save the user_id and message_id so we can easily find
    # the message key later
    client.set(f"user_id:<{user_id}>msg_id:<{message_id}>", key)
    client.hset(key, mapping={"message_id": int(message_id)})


def _record(client, user_id, msg_id, _type, value):
    client.set(f"user_id:<{user_id}>msg_id:<{msg_id}>:{_type}", value)


def save_embedding(client, user_id, message_text, embedding):
    return _record_embedding(client, user_id, message_text, embedding)


def update_embedding(client, user_id, message_id, message_text, embedding):
    """
    Update the embedding record for the message after it was edited by the user
    or automatic rewriting.
    """
    key = client.get(f"user_id:<{user_id}>msg_id:<{message_id}>")
    mapping = {"message": message_text,
               "message_embedding": np.array(embedding, dtype=np.float32).tobytes()}
    # delete the record connecting the key to user_id and msg_id
    client.delete(f"user_id:<{user_id}>msg_id:<{message_id}>")
    client.hset(key, mapping=mapping)


def update_message_id(client, key, user_id, message_id):
    _update_message_id(client, key, user_id, message_id)


def save_message(client, user_id, message_id, message_text, embedding):
    # Add the message to the cache
    _record(client, user_id, message_id, "text", message_text)
    _record(client, user_id, message_id, "time", datetime.now().timestamp())
    

def update_message(client, user_id, message_id, message_text):
    # Update the message in the cache
    _record(client, user_id, message_id, "text", message_text)


def wait_for_approval(client, chat_id, message_id):
    client.set(f"appr:<{chat_id}>:<{message_id}>", datetime.now().timestamp())


def remove_approval(client, chat_id, message_id):
    client.delete(f"appr:<{chat_id}>:<{message_id}>")