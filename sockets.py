import socketio

sio_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[]
)

sio_app = socketio.ASGIApp(
    socketio_server=sio_server,
    socketio_path='/sockets'
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
    rooms['floor07'].append({'client_id': sid, 'img_url': "https://i.imgur"})
    print(rooms)
    print(f'{sid}: joined floor07')

@sio_server.event
async def CS_CHAT(sid, data):
    room_id = data.get('room_id')
    user_name = data.get('user_name')
    message = data.get('message')
    # print(data)


    print(f'room_id: {room_id}, user_name: {user_name}, message: {message}')

    # 클라이언트가 방을 변경하는 경우
    # 기존 방 아이디와 같은 message를 보내면 해당 방에서 제거하고 m 방에 추가
    # 이후에 이 부분은 Redis를 사용하여 처리할 예정
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
async def disconnect(sid):
    print(f'{sid}: disconnected')
