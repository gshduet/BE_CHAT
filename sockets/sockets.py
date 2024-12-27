import socketio
from core.databases import get_redis
from urllib.parse import parse_qs

sio_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[]
)

sio_app = socketio.ASGIApp(
    socketio_server=sio_server,
    socketio_path='/sockets'
)

redis_client = get_redis()

@sio_server.event
async def connect(sid, environ):
    # 클라이언트가 보낸 데이터에서 client_id 추출
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

    # 기본적으로 floor07 방에 클라이언트 추가
    default_room = "floor07"
    client_data = {"client_id": client_id, "img_url": "https://i.imgur"}
    await redis_client.hset(f"rooms:{default_room}", client_id, str(client_data))
    await redis_client.hset("clients", client_id, {"room_id": default_room, "img_url": "https://i.imgur"})
    
    print(f'{client_id}: joined {default_room}')

@sio_server.event
async def CS_CHAT(sid, data):
    # client_id = data.get('client_id')
    client_id = "user_id"
    room_id = data.get('room_id')
    user_name = data.get('user_name')
    message = data.get('message')
    print(f'room_id: {room_id}, user_name: {user_name}, message: {message}')

    current_room = (await redis_client.hget("clients", client_id))["room_id"]

    if message == current_room:
        new_room = "m"
        # 방 이동 처리
        await redis_client.hdel(f"rooms:{current_room}", client_id)
        await redis_client.hset(f"rooms:{new_room}", client_id, {"client_id": client_id, "img_url": "https://i.imgur"})
        await redis_client.hset("clients", client_id, {"room_id": new_room})
        print(f'{user_name} moved to room {new_room}')

    # 해당 room에 있는 모든 클라이언트에게 메시지를 보냄
    room_clients = await redis_client.hgetall(f"rooms:{room_id}")
    for client_id, client_info in room_clients.items():
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
    room_clients = await redis_client.hgetall(f"rooms:{room_id}")
    for client_id, client_info in room_clients.items():
        await sio_server.emit('SC_MOVEMENT_INFO', {
            'room_id': room_id,
            'user_id': client_id,
            'position_x': position_x,
            'position_y': position_y
        }, to=client_id)

@sio_server.event
async def disconnect(sid):
    print(f'{sid}: disconnected')

    # sid로 client_id를 조회
    client_id = await redis_client.hget("sid_to_client", sid)
    if not client_id:
        print(f"Disconnect failed: client_id not found for sid {sid}")
        return

    # 클라이언트 정보를 제거
    client_info = await redis_client.hget("clients", client_id)
    if not client_info:
        print(f"Client data not found for {client_id}")
        return

    room_id = client_info["room_id"]
    await redis_client.hdel(f"rooms:{room_id}", client_id)
    await redis_client.hdel("clients", client_id)

    # 매핑 데이터 제거
    await redis_client.hdel("sid_to_client", sid)
    await redis_client.hdel("client_to_sid", client_id)

    print(f'{client_id}: removed from {room_id}')