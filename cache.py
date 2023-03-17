from typing import List, Union

from datetime import datetime

import numpy as np

import redis
from redis.commands.search.indexDefinition import (
    IndexDefinition,
    IndexType
)
from redis.commands.search.query import Query
from redis.commands.search.field import (
    TextField,
    VectorField
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
        client,
        index_name=INDEX_NAME, 
        embedding_dim=EMBEDDING_DIM, 
        distance_metric=DISTANCE_METRIC,
        prefix=PREFIX):
    try:
        client.ft(INDEX_NAME).info()
        return
    except:
        pass
    
    user_id = TextField(name="user_id")
    message_id = TextField(name="message_id")
    message = TextField(name="message")
    message_embedding = VectorField("message_embedding",
                                    "FLAT", {
                                        "TYPE": "FLOAT32",
                                        "DIM":  embedding_dim,
                                        "DISTANCE_METRIC": distance_metric,
                                        "INITIAL_CAP": 1000,
                                    }
    )

    fields = [user_id, message_id, message, message_embedding]

    client.ft(index_name).create_index(
                        fields = fields,
                        definition = IndexDefinition(
                                            prefix=[prefix], 
                                            index_type=IndexType.HASH)
    )


def search_redis(
    redis_client: redis.Redis,
    user_id: Union[int, str],
    user_query: str,
    index_name: str = INDEX_NAME,
    vector_field: str = "message_embedding",
    return_fields: list = ["message", "message_id", "user_id", "vector_score"],
    hybrid_fields = "*",
    k: int = 20,
    print_results: bool = False,
    ) -> List[dict]:

    # Creates embedding vector from user query
    embedded_query = embed_text(user_query)

    user_id = str(user_id)

    # Prepare the Query
    base_query = f'{hybrid_fields}=>[KNN {k} @{vector_field} $vector AS vector_score]'
    query = (
        Query(base_query)
         .add_filter("user_id", user_id)
         .return_fields(*return_fields)
         .sort_by("vector_score")
         .paging(0, k)
         .dialect(2)
    )
    params_dict = {"vector": np.array(embedded_query).astype(dtype=np.float32).tobytes()}

    # perform vector search
    results = redis_client.ft(index_name).search(query, params_dict)
    if print_results:
        for i, article in enumerate(results.docs):
            score = 1 - float(article.vector_score)
            print(f"{i}. {article.title} (Score: {round(score ,3) })")
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


def _record_embedding(client, user_id, msg_id, 
                      message, message_embedding,
                      prefix=PREFIX):
    message_embedding = np.array(message_embedding, dtype=np.float32).tobytes()
    key = f"{prefix}:<{user_id}><{msg_id}>"
    mapping = {"user_id": str(user_id),
               "message_id": str(msg_id),
               "message": message, 
               "message_embedding": message_embedding}
    client.hset(key, mapping = mapping)


def _record(client, user_id, msg_id, _type, value):
    client.set(f"user_id:<{user_id}>msg_id:<{msg_id}>:{_type}", value)


def save_message(client, user_id, message_id, message_text):
    # Add the message to the cache
    _record(client, user_id, message_id, "text", message_text)
    _record(client, user_id, message_id, "time", datetime.now().timestamp())

    # embed the message
    try:
        embedding = embed_text(message_text)
        _record_embedding(client, user_id, message_id, message_text, embedding)
    except:
        print ("Embedding failed for message: ", message_text)
        print ("This is most likely the API's fault.")
    


def update_message(client, user_id, message_id, message_text):
    # Update the message in the cache
    _record(client, user_id, message_id, "text", message_text)
    # embed the message
    try:
        embedding = embed_text(message_text)
        _record_embedding(client, user_id, message_id, message_text, embedding)
    except:
        print ("Embedding failed for message: ", message_text)
        print ("This is most likely the API's fault.")
    

def wait_for_approval(client, chat_id, message_id):
    client.set(f"appr:<{chat_id}>:<{message_id}>", datetime.now().timestamp())


def remove_approval(client, chat_id, message_id):
    client.delete(f"appr:<{chat_id}>:<{message_id}>")