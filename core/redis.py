from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError
from core.config import settings
import asyncio
from functools import wraps

ROOMS_KEY_TEMPLATE = settings.rooms_key_template
CLIENT_KEY_TEMPLATE = settings.client_key_template
SID_KEY_TEMPLATE = settings.sid_key_template
DISCONNECTED_CLIENT_KEY_TEMPLATE = settings.disconnected_client_key_template
MEETING_ROOM_KEY_TEMPLATE = settings.meeting_room_key_template
CLIENT_SID_KEY_TEMPLATE = settings.client_sid_key_template

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


def with_redis_retry(func):
    """
    Redis 작업 실행 시 연결 오류가 발생하면 재시도하는 데코레이터입니다.
    최대 3번까지 재시도하며, 실패 시 1초 간격으로 대기합니다.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        retries = 0
        last_error = None

        while retries < MAX_RETRIES:
            try:
                return await func(*args, **kwargs)
            except (RedisError, ConnectionError) as e:
                last_error = e
                retries += 1
                if retries < MAX_RETRIES:
                    print(
                        f"Redis operation failed: {e}. Retrying... (attempt {retries}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(RETRY_DELAY)

        print(f"Redis operation failed after {MAX_RETRIES} attempts: {last_error}")
        raise last_error

    return wrapper


@with_redis_retry
async def add_to_room(room_id: str, client_id: str, redis_client: Redis):
    await redis_client.sadd(ROOMS_KEY_TEMPLATE.format(room_id=room_id), client_id)


@with_redis_retry
async def remove_from_room(room_id: str, client_id: str, redis_client: Redis):
    await redis_client.srem(ROOMS_KEY_TEMPLATE.format(room_id=room_id), client_id)


@with_redis_retry
async def get_room_clients(room_id: str, redis_client: Redis):
    return await redis_client.smembers(ROOMS_KEY_TEMPLATE.format(room_id=room_id))


@with_redis_retry
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


@with_redis_retry
async def remove_from_meeting_room(room_id: str, client_id: str, redis_client: Redis):
    await redis_client.hdel(
        MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), client_id
    )


@with_redis_retry
async def get_meeting_room_clients(room_id: str, redis_client: Redis):
    data = await redis_client.hgetall(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id))
    return [k for k in data.keys() if k != "title"]


@with_redis_retry
async def get_meeting_room_title(room_id: str, redis_client: Redis):
    return await redis_client.hget(
        MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id), "title"
    )


@with_redis_retry
async def delete_meeting_room(room_id: str, redis_client: Redis):
    await redis_client.delete(MEETING_ROOM_KEY_TEMPLATE.format(room_id=room_id))


@with_redis_retry
async def get_all_meeting_rooms(redis_client: Redis):
    room_keys = await redis_client.keys("meeting_room:*")
    rooms = []
    for rk in room_keys:
        room_id = rk.split(":")[-1]
        title = await get_meeting_room_title(room_id, redis_client)
        clients = await get_meeting_room_clients(room_id, redis_client)
        rooms.append({"room_id": room_id, "title": title, "clients": clients})
    return rooms


@with_redis_retry
async def set_client_info(client_id: str, info: dict, redis_client):
    # 모든 값을 문자열로 변환
    info = {key: str(value) if not isinstance(value, (bytes, str, int, float)) else value for key, value in info.items()}
    await redis_client.hset(CLIENT_KEY_TEMPLATE.format(client_id=client_id), mapping=info)



@with_redis_retry
async def get_client_info(client_id: str, redis_client: Redis):
    return await redis_client.hgetall(CLIENT_KEY_TEMPLATE.format(client_id=client_id))


@with_redis_retry
async def delete_client_info(client_id: str, redis_client: Redis):
    await redis_client.delete(CLIENT_KEY_TEMPLATE.format(client_id=client_id))


@with_redis_retry
async def set_sid_mapping(client_id: str, sid: str, redis_client: Redis):
    await redis_client.set(SID_KEY_TEMPLATE.format(sid=sid), client_id)
    await redis_client.set(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id), sid)


@with_redis_retry
async def get_client_id_by_sid(sid: str, redis_client: Redis):
    return await redis_client.get(SID_KEY_TEMPLATE.format(sid=sid))


@with_redis_retry
async def get_sid_by_client_id(client_id: str, redis_client: Redis):
    return await redis_client.get(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id))


# 저장된 sid들을 반환하는 함수
@with_redis_retry
async def get_all_sids(redis_client: Redis):
    sids = await redis_client.keys("sid:*")
    return [sid.split(":")[-1] for sid in sids]


@with_redis_retry
async def delete_sid_mapping(sid: str, redis_client: Redis):
    client_id = await redis_client.get(SID_KEY_TEMPLATE.format(sid=sid))
    await redis_client.delete(SID_KEY_TEMPLATE.format(sid=sid))
    if client_id:
        await redis_client.delete(CLIENT_SID_KEY_TEMPLATE.format(client_id=client_id))


@with_redis_retry
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


@with_redis_retry
async def get_disconnected_client(client_id: str, redis_client: Redis):
    return await redis_client.hgetall(
        DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id)
    )


@with_redis_retry
async def delete_disconnected_client(client_id: str, redis_client: Redis):
    await redis_client.delete(
        DISCONNECTED_CLIENT_KEY_TEMPLATE.format(client_id=client_id)
    )


# redis 큐 관련 함수
@with_redis_retry
async def enqueue_connection_request(
    redis_client: Redis,
    sid: str,
    client_id: str,
    user_name: str,
):
    await redis_client.rpush(
        "connection_requests", f"{sid}|{client_id}|{user_name}"
    )


@with_redis_retry
async def dequeue_connection_request(redis_client: Redis):
    request = await redis_client.lpop("connection_requests")
    if request:
        sid, client_id, user_name = request.split("|")
        return {
            "sid": sid,
            "client_id": client_id,
            "user_name": user_name,
        }
    return None
