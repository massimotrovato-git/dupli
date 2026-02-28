import os
import redis
from rq import Worker, Queue
from rq.connections import Connection

def main():
    r = redis.from_url(os.getenv("REDIS_URL"))
    with Connection(r):
        q = Queue("exec")
        w = Worker([q])
        w.work(with_scheduler=True)

if __name__ == "__main__":
    main()
