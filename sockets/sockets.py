import socketio
import redis.asyncio as redis
from urllib.parse import parse_qs
import asyncio

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
    cors_allowed_origins=[]
)

sio_app = socketio.ASGIApp(
    socketio_server=sio_server,
    socketio_path='/sio/sockets'
)

# Redis 초기화 비동기로 실행
# asyncio.run(init_redis())

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
    await redis_client.hset("sid_to_client", sid, client_id)
    await redis_client.hset("client_to_sid", client_id, sid)

    print(f'{client_id} ({sid}): mapping saved')

    # 기본적으로 floor07 방에 클라이언트 추가
    default_room = "floor07"
    await redis_client.sadd(f"rooms:{default_room}", client_id)
    await redis_client.hset("clients", client_id, str({"room_id": default_room, "img_url": "https://i.imgur"}))
    
    print(f'{client_id}: joined {default_room}')

@sio_server.event
async def CS_CHAT(sid, data):
    client_id = "user_id"
    room_id = data.get('room_id')
    user_name = data.get('user_name')
    message = data.get('message')
    print(f'room_id: {room_id}, user_name: {user_name}, message: {message}')

    client_data = await redis_client.hget("clients", client_id)
    if client_data:
        client_data = eval(client_data)  # 문자열을 딕셔너리로 변환
        current_room = client_data["room_id"]

        if message == current_room:
            new_room = "m"
            # 방 이동 처리
            await redis_client.srem(f"rooms:{current_room}", client_id)
            await redis_client.sadd(f"rooms:{new_room}", client_id)
            await redis_client.hset("clients", client_id, str({"room_id": new_room}))
            print(f'{user_name} moved to room {new_room}')

        # 해당 room에 있는 모든 클라이언트에게 메시지를 보냄
        room_clients = await redis_client.smembers(f"rooms:{room_id}")
        for client_id in room_clients:
            await sio_server.emit('SC_CHAT', {
                'user_name': user_name,
                'message': message
            }, to=client_id)

@sio_server.event
async def CS_MOVEMENT_INFO(sid, data):
    client_id = data.get('client_id')
    room_id = data.get('room_id')
    position_x = data.get('position_x')
    position_y = data.get('position_y')

    print(f'client_id: {client_id}, room_id: {room_id}, position_x: {position_x}, position_y: {position_y}')

    # 해당 room에 있는 모든 클라이언트에게 움직임 정보를 전송
    room_clients = await redis_client.smembers(f"rooms:{room_id}")
    for client_id in room_clients:
        await sio_server.emit('SC_MOVEMENT_INFO', {
            'room_id': room_id,
            'user_id': client_id,
            'position_x': position_x,
            'position_y': position_y
        }, to=client_id)

@sio_server.event
async def disconnect(sid):
    print(f'{sid}: disconnected')

    client_id = await redis_client.hget("sid_to_client", sid)
    if not client_id:
        print(f"Disconnect failed: client_id not found for sid {sid}")
        return

    # 클라이언트 정보를 제거
    client_info = await redis_client.hget("clients", client_id)
    if client_info:
        client_data = eval(client_info)
        room_id = client_data.get("room_id")
        await redis_client.srem(f"rooms:{room_id}", client_id)
        await redis_client.hdel("clients", client_id)

    # 매핑 데이터 제거
    await redis_client.hdel("sid_to_client", sid)
    await redis_client.hdel("client_to_sid", client_id)

    print(f'{client_id}: removed')
