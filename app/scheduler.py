import os

from redis import Redis
from rq import Queue

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_password = os.getenv("REDIS_PASSWORD") or None

queue = Queue(connection=Redis(host=redis_host, port=redis_port, password=redis_password))
