import socketio
import redis.asyncio as redis
import json
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
            print("Redis connected successfully!")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        redis_client = None

sio_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[] # 추후 CORS 설정 필요
)

sio_app = socketio.ASGIApp(
    socketio_server=sio_server,
    socketio_path='/sio/sockets'
)

@sio_server.event
async def connect(sid, environ):
    query_string = environ.get("QUERY_STRING", "")
    query_params = parse_qs(query_string)
    client_id = query_params.get("client_id", [None])[0]

    if not client_id:
        print(f"Connection rejected: client_id not provided")
        return False

    print(f'{client_id} ({sid}): connected')

     # sid와 client_id 매핑 저장
    try:
        await redis_client.hset("app:sid_to_client", sid, client_id)
        await redis_client.hset("app:client_to_sid", client_id, sid)

        default_room = "floor07"
        await redis_client.sadd(f"app:rooms:{default_room}", client_id)
        client_data = {"room_id": default_room, "img_url": "https://i.imgur"}
        await redis_client.hset("app:clients", client_id, json.dumps(client_data))

        print(f'{client_id}: joined {default_room}')
    except Exception as e:
        print(f"Error during connect: {e}")
        return False

@sio_server.event
async def CS_CHAT(sid, data):
    try:
        room_id = data.get('room_id')
        user_name = data.get('user_name')
        message = data.get('message')

        if not (room_id and user_name and message):
            print("Invalid chat data")
            return

        client_id = await redis_client.hget("app:sid_to_client", sid)
        if not client_id:
            print(f"Chat failed: client_id not found for sid {sid}")
            return

        client_data = await redis_client.hget("app:clients", client_id)
        if client_data:
            client_data = json.loads(client_data)
            current_room = client_data["room_id"]

            if message == current_room:
                new_room = "m"
                await redis_client.srem(f"app:rooms:{current_room}", client_id)
                await redis_client.sadd(f"app:rooms:{new_room}", client_id)
                client_data["room_id"] = new_room
                await redis_client.hset("app:clients", client_id, json.dumps(client_data))
                print(f'{user_name} moved to room {new_room}')

            room_clients = await redis_client.smembers(f"app:rooms:{room_id}")
            for client in room_clients:
                await sio_server.emit('SC_CHAT', {
                    'user_name': user_name,
                    'message': message
                }, to=client)
    except Exception as e:
        print(f"Error during CS_CHAT: {e}")

@sio_server.event
async def CS_MOVEMENT_INFO(sid, data):
    try:
        client_id = data.get('client_id')
        room_id = data.get('room_id')
        position_x = data.get('position_x')
        position_y = data.get('position_y')

        if not (client_id and room_id and isinstance(position_x, (int, float)) and isinstance(position_y, (int, float))):
            print("Invalid movement data")
            return

        room_clients = await redis_client.smembers(f"app:rooms:{room_id}")
        for client in room_clients:
            await sio_server.emit('SC_MOVEMENT_INFO', {
                'room_id': room_id,
                'user_id': client_id,
                'position_x': position_x,
                'position_y': position_y
            }, to=client)
    except Exception as e:
        print(f"Error during CS_MOVEMENT_INFO: {e}")

@sio_server.event
async def disconnect(sid):
    try:
        client_id = await redis_client.hget("app:sid_to_client", sid)
        if not client_id:
            print(f"Disconnect failed: client_id not found for sid {sid}")
            return

        client_info = await redis_client.hget("app:clients", client_id)
        if client_info:
            client_data = json.loads(client_info)
            room_id = client_data.get("room_id")
            await redis_client.srem(f"app:rooms:{room_id}", client_id)
            await redis_client.hdel("app:clients", client_id)

        await redis_client.hdel("app:sid_to_client", sid)
        await redis_client.hdel("app:client_to_sid", client_id)

        print(f'{client_id}: removed')
    except Exception as e:
        print(f"Error during disconnect: {e}")
