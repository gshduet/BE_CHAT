from redis.asyncio import Redis
from core.config import settings

ROOMS_KEY_TEMPLATE = settings.rooms_key_template
CLIENT_KEY_TEMPLATE = settings.client_key_template
SID_KEY_TEMPLATE = settings.sid_key_template
DISCONNECTED_CLIENT_KEY_TEMPLATE = settings.disconnected_client_key_template
MEETING_ROOM_KEY_TEMPLATE = settings.meeting_room_key_template
CLIENT_SID_KEY_TEMPLATE = settings.client_sid_key_template


async def add_to_room(room_id: str, client_id: str, redis_client: Redis):
    await redis_client.sadd(ROOMS_KEY_TEMPLATE.format(room_id=room_id), client_id)


async def remove_from_room(room_id: str, client_id: str, redis_client: Redis):
    await redis_client.srem(ROOMS_KEY_TEMPLATE.format(room_id=room_id), client_id)


async def get_room_clients(room_id: str, redis_client: Redis):
    return await redis_client.smembers(ROOMS_KEY_TEMPLATE.format(room_id=room_id))


async def add_to_meeting_room(
    room_id: str, title: str, client_id: str, redis_client: Redis
):
    if title:
        await redis_client.hset(
            MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), "title", title
        )
    await redis_client.hset(
        MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), client_id, ""
    )


async def remove_from_meeting_room(room_id: str, client_id: str, redis_client: Redis):
    await redis_client.hdel(
        MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), client_id
    )


async def get_meeting_room_clients(room_id: str, redis_client: Redis):
    data = await redis_client.hgetall(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id))
    return [k for k in data.keys() if k != "title"]


async def get_meeting_room_title(room_id: str, redis_client: Redis):
    return await redis_client.hget(
        MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), "title"
    )


async def delete_meeting_room(room_id: str, redis_client: Redis):
    await redis_client.delete(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id))


async def get_all_meeting_rooms(redis_client: Redis):
    room_keys = await redis_client.keys("meeting_room:*")
    rooms = []
    for rk in room_keys:
        room_id = rk.split(":")[-1]
        title = await get_meeting_room_title(room_id, redis_client)
        clients = await get_meeting_room_clients(room_id, redis_client)
        rooms.append({"room_id": room_id, "title": title, "clients": clients})
    return rooms


async def set_client_info(client_id: str, info: dict, redis_client: Redis):
    await redis_client.hset(
        CLIENT_KEY_TEMPLATE.format(client_id=client_id), mapping=info
    )


async def get_client_info(client_id: str, redis_client: Redis):
    return await redis_client.hgetall(CLIENT_KEY_TEMPLATE.format(client_id=client_id))


async def delete_client_info(client_id: str, redis_client: Redis):
    await redis_client.delete(CLIENT_KEY_TEMPLATE.format(client_id=client_id))


async def set_sid_mapping(client_id: str, sid: str, redis_client: Redis):
    await redis_client.set(SID_KEY_TEMPLATE.format(sid=sid), client_id)
    await redis_client.set(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id), sid)


async def get_client_id_by_sid(sid: str, redis_client: Redis):
    return await redis_client.get(SID_KEY_TEMPLATE.format(sid=sid))


async def get_sid_by_client_id(client_id: str, redis_client: Redis):
    return await redis_client.get(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id))


async def delete_sid_mapping(sid: str, redis_client: Redis):
    client_id = await redis_client.get(SID_KEY_TEMPLATE.format(sid=sid))
    await redis_client.delete(SID_KEY_TEMPLATE.format(sid=sid))
    if client_id:
        await redis_client.delete(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id))


async def set_disconnected_client(client_id: str, info: dict, redis_client: Redis):
    if not info:
        print(f"Error: Cannot set disconnected client {client_id}, info is empty")
        return
    try:
        await redis_client.hset(
            DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id), mapping=info
        )
    except Exception as e:
        print(f"Redis Error: {e}")


async def get_disconnected_client(client_id: str, redis_client: Redis):
    return await redis_client.hgetall(
        DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id)
    )


async def delete_disconnected_client(client_id: str, redis_client: Redis):
    await redis_client.delete(
        DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id)
    )
