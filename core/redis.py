import redis.asyncio as redis
from urllib.parse import parse_qs

# Ubuntu Redis 사용 test code
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_DB = 0

# Redis 클라이언트 생성
redis_client = None

async def init_redis():
    global redis_client
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        # Redis 연결 테스트
        if await redis_client.ping():
            print("Redis connected")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        redis_client = None