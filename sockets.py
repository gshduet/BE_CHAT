import socketio

sio_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[]
)

sio_app = socketio.ASGIApp(
    socketio_server=sio_server,
    socketio_path='/sio/sockets'
)

# 방 정보를 관리할 딕셔너리
rooms = {}
rooms['floor07'] = []
rooms['m'] = []

# 클라이언트 정보를 관리할 딕셔너리
clients = {'user1': {'img_url': "https://i.imgur", 'room_id': 'floor07'}}

@sio_server.event
async def connect(sid, environ):
    print(f'{sid}: connected')
    if 'floor07' in rooms:
        rooms['floor07'].append({'client_id': sid, 'img_url': "https://i.imgur"})
        print(rooms)
        print(f'{sid}: join floor07')
    else:
        print(f'Error: Room floor07 does not exist.')

@sio_server.event
async def CS_CHAT(sid, data):
    # 데이터 유효성 검사
    if not isinstance(data, dict):
        print(f'Error: Invalid data format: {data}')
        return

    room_id = data.get('room_id')
    user_name = data.get('user_name')
    message = data.get('message')

    if not room_id or not user_name or not message:
        print(f'Error: Missing required fields in data: {data}')
        return

    if user_name not in clients:
        print(f'Error: User {user_name} does not exist.')
        return

    if room_id not in rooms:
        print(f'Error: Room {room_id} does not exist.')
        return

    print(f'room_id: {room_id}, user_name: {user_name}, message: {message}')

    # 클라이언트가 방을 변경하는 경우
    if message == clients[user_name]['room_id']:
        room_id = 'm'
        old_room = clients[user_name]['room_id']
        rooms[old_room] = [
            client for client in rooms[old_room]
            if client['client_id'] != user_name
        ]
        clients[user_name]['room_id'] = room_id
        if room_id not in rooms:
            rooms[room_id] = []
        rooms[room_id].append({'client_id': user_name, 'img_url': clients[user_name]['img_url']})
        print(f'{user_name} moved to room {room_id}')

    # 해당 room에 있는 모든 클라이언트에게 메세지를 보냄
    for client in rooms[room_id]:
        await sio_server.emit('SC_CHAT', {
            'user_name': user_name,
            'message': message
        }, to=client['client_id'])

@sio_server.event
async def CS_MOVEMENT_INFO(sid, data):
    print(f'client send CS_MOVEMENT_INFO')

    # 데이터 유효성 검사
    if not isinstance(data, dict):
        print(f'Error: Invalid data format: {data}')
        return

    user_id = data.get('user_id')
    room_id = data.get('room_id')
    position_x = data.get('position_x')
    position_y = data.get('position_y')

    if not user_id or not room_id or position_x is None or position_y is None:
        print(f'Error: Missing data: {data}')
        return

    if user_id not in clients:
        print(f'Error: User {user_id} does not exist.')
        return

    if room_id not in rooms:
        print(f'Error: Room {room_id} does not exist.')
        return

    print(f'user_id: {user_id}, room_id: {room_id}, position_x: {position_x}, position_y: {position_y}')

    # 해당 room에 있는 모든 클라이언트에게 움직임 정보를 전송
    for client in rooms[room_id]:
        await sio_server.emit('SC_MOVEMENT_INFO', {
            'room_id': room_id,
            'user_id': user_id,
            'position_x': position_x,
            'position_y': position_y,
            'img_url': clients[user_id]['img_url']
        }, to=client['client_id'])

@sio_server.event
async def disconnect(sid):
    print(f'{sid}: disconnected')
