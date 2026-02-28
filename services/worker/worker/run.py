import os
import sys
import redis
from rq import Worker, Queue


def main():
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        print("FATAL: REDIS_URL is required but not set.", flush=True)
        sys.exit(1)

    conn = redis.from_url(redis_url)
    q = Queue("exec", connection=conn)
    w = Worker([q], connection=conn)
    print("Worker started, listening on queue 'exec'...", flush=True)
    w.work(with_scheduler=True)


if __name__ == "__main__":
    main()
