import redis.asyncio as redis
from dotenv import load_dotenv
import os

load_dotenv()

REDIS_HOST = os.environ['REDIS_HOST']
REDIS_PORT = int(os.environ['REDIS_PORT'])
REDIS_DB = int(os.environ['REDIS_DB'])
redis_client = None
ROOMS_KEY_TEMPLATE = os.environ['ROOMS_KEY_TEMPLATE']
CLIENT_KEY_TEMPLATE = os.environ['CLIENT_KEY_TEMPLATE']
SID_KEY_TEMPLATE = os.environ['SID_KEY_TEMPLATE']
DISCONNECTED_CLIENT_KEY_TEMPLATE = os.environ['DISCONNECTED_CLIENT_KEY_TEMPLATE']
MEETING_ROOM_KEY_TEMPLATE = os.environ['MEETING_ROOM_KEY_TEMPLATE']
CLIENT_SID_KEY_TEMPLATE = os.environ['CLIENT_SID_KEY_TEMPLATE']

async def init_redis():
    global redis_client
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    await redis_client.ping()

async def add_to_room(room_id, client_id):
    await redis_client.sadd(ROOMS_KEY_TEMPLATE.format(room_id=room_id), client_id)

async def remove_from_room(room_id, client_id):
    await redis_client.srem(ROOMS_KEY_TEMPLATE.format(room_id=room_id), client_id)

async def get_room_clients(room_id):
    return await redis_client.smembers(ROOMS_KEY_TEMPLATE.format(room_id=room_id))

async def add_to_meeting_room(room_id, title, client_id):
    if title:
        await redis_client.hset(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), "title", title)
    await redis_client.hset(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), client_id, "")

async def remove_from_meeting_room(room_id, client_id):
    await redis_client.hdel(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), client_id)

async def get_meeting_room_clients(room_id):
    data = await redis_client.hgetall(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id))
    return [k for k in data.keys() if k != "title"]

async def get_meeting_room_title(room_id):
    return await redis_client.hget(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), "title")

async def delete_meeting_room(room_id):
    await redis_client.delete(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id))

async def get_all_meeting_rooms():
    room_keys = await redis_client.keys("meeting_room:*")
    rooms = []
    for rk in room_keys:
        room_id = rk.split(":")[-1]
        title = await get_meeting_room_title(room_id)
        clients = await get_meeting_room_clients(room_id)
        rooms.append({"room_id": room_id, "title": title, "clients": clients})
    return rooms

async def set_client_info(client_id, info):
    await redis_client.hset(CLIENT_KEY_TEMPLATE.format(client_id=client_id), mapping=info)

async def get_client_info(client_id):
    return await redis_client.hgetall(CLIENT_KEY_TEMPLATE.format(client_id=client_id))

async def delete_client_info(client_id):
    await redis_client.delete(CLIENT_KEY_TEMPLATE.format(client_id=client_id))

async def set_sid_mapping(client_id, sid):
    await redis_client.set(SID_KEY_TEMPLATE.format(sid=sid), client_id)
    await redis_client.set(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id), sid)

async def get_client_id_by_sid(sid):
    return await redis_client.get(SID_KEY_TEMPLATE.format(sid=sid))

async def get_sid_by_client_id(client_id):
    return await redis_client.get(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id))

async def delete_sid_mapping(sid):
    client_id = await redis_client.get(SID_KEY_TEMPLATE.format(sid=sid))
    await redis_client.delete(SID_KEY_TEMPLATE.format(sid=sid))
    if client_id:
        await redis_client.delete(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id))

# 재접속 시 사용
async def set_disconnected_client(client_id, info):
    if not info:
        print(f"Error: Cannot set disconnected client {client_id}, info is empty")
        return
    try:
        await redis_client.hset(DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id), mapping=info)
    except Exception as e:
        print(f"Redis Error: {e}")

async def get_disconnected_client(client_id):
    return await redis_client.hgetall(DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id))

async def delete_disconnected_client(client_id):
    await redis_client.delete(DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id))
