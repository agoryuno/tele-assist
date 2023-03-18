from typing import Union
import time
from cache import get_redis_client, embed_text, search_redis


async def search_query(
        user_id: Union[int, str],
        user_query: str,
        pause: int = 2):
    redis_client = get_redis_client()
    # embed the user query
    while True:
        try:
            user_query_embedding = embed_text(user_query)
            break
        except:
            print (f"Embedding failed, retrying in {pause} seconds...")
            time.sleep(pause)
    
    return search_redis(redis_client,
                        user_id,
                        user_query_embedding,)