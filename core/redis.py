import redis.asyncio as redis
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# Redis 호스트, 포트, DB 번호
REDIS_HOST = os.environ['REDIS_HOST']
REDIS_PORT = int(os.environ['REDIS_PORT'])
REDIS_DB = int(os.environ['REDIS_DB'])

redis_client = None

# Redis 키 템플릿을 환경변수에서만 로드
ROOMS_KEY_TEMPLATE = os.environ['ROOMS_KEY_TEMPLATE']
CLIENT_KEY_TEMPLATE = os.environ['CLIENT_KEY_TEMPLATE']
SID_KEY_TEMPLATE = os.environ['SID_KEY_TEMPLATE']
DISCONNECTED_CLIENT_KEY_TEMPLATE = os.environ['DISCONNECTED_CLIENT_KEY_TEMPLATE']
MEETING_ROOM_KEY_TEMPLATE = os.environ['MEETING_ROOM_KEY_TEMPLATE']

# Redis 초기화 함수
async def init_redis():
    global redis_client
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        if await redis_client.ping():
            print("Redis connected")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        redis_client = None

# 방 관련 함수들
async def add_to_room(room_id, client_id):
    await redis_client.sadd(ROOMS_KEY_TEMPLATE.format(room_id=room_id), client_id)

async def remove_from_room(room_id, client_id):
    await redis_client.srem(ROOMS_KEY_TEMPLATE.format(room_id=room_id), client_id)

async def get_room_clients(room_id):
    return await redis_client.smembers(ROOMS_KEY_TEMPLATE.format(room_id=room_id))

# 미팅룸 관련 함수들
async def add_to_meeting_room(room_id, client_id):
    await redis_client.sadd(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), client_id)

async def remove_from_meeting_room(room_id, client_id):
    await redis_client.srem(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), client_id)

async def get_meeting_room_clients(room_id):
    return await redis_client.smembers(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id))

async def delete_meeting_room(room_id):
    await redis_client.delete(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id))

# 클라이언트 관련 함수들
async def set_client_info(client_id, info):
    await redis_client.hset(CLIENT_KEY_TEMPLATE.format(client_id=client_id), mapping=info)

async def get_client_info(client_id):
    return await redis_client.hgetall(CLIENT_KEY_TEMPLATE.format(client_id=client_id))

async def delete_client_info(client_id):
    await redis_client.delete(CLIENT_KEY_TEMPLATE.format(client_id=client_id))

# SID 관련 함수들
async def set_sid_mapping(client_id, sid):
    await redis_client.set(SID_KEY_TEMPLATE.format(sid=sid), client_id)

async def get_client_id_by_sid(sid):
    return await redis_client.get(SID_KEY_TEMPLATE.format(sid=sid))

async def delete_sid_mapping(sid):
    await redis_client.delete(SID_KEY_TEMPLATE.format(sid=sid))

# 재접속 대기 클라이언트 관련 함수들
async def set_disconnected_client(client_id, info):
    await redis_client.hset(DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id), mapping=info)

async def get_disconnected_client(client_id):
    return await redis_client.hgetall(DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id))

async def delete_disconnected_client(client_id):
    await redis_client.delete(DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id))
