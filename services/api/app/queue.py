import os
import redis
from rq import Queue

def get_queue() -> Queue:
    r = redis.from_url(os.getenv("REDIS_URL"))
    return Queue("exec", connection=r, default_timeout=60)
