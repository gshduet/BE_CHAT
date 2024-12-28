import socketio
from urllib.parse import parse_qs

sio_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[]
)

sio_app = socketio.ASGIApp(
    socketio_server=sio_server,
    socketio_path='/sio/sockets'
)

# 추후 Redis를 사용하여 데이터를 저장할 예정 {
# 방 정보를 관리할 딕셔너리
rooms = {}
default_room = "floor07"
test_meeting_room = "meeting_room"

# 클라이언트 정보를 관리할 딕셔너리
clients = {'user1': {'img_url': "https://i.imgur", 'room_id': 'floor07'}}

# sid와 client_id 매핑을 저장할 딕셔너리
client_to_sid = {}
# }


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

    # 추후 Redis를 사용하여 데이터를 저장할 예정 {
    # sid와 client_id 매핑 저장
    client_to_sid[client_id] = sid

    # 기본적으로 floor07 방에 클라이언트 추가
    if default_room not in rooms:
        rooms[default_room] = []
    rooms[default_room].append({'client_id': client_id})
    # }

    print(f'{client_id}: joined {default_room}')



@sio_server.event
async def CS_CHAT(sid, data):
    # 데이터 유효성 검사
    if not isinstance(data, dict):
        print(f'Error: Invalid data format: {data}')
        return

    room_id = data.get('room_id')
    client_id = data.get('client_id')
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
    # 자신의 room_id와 같은 메세지를 보내면 test_meeting_room으로 방을 변경
    if message == clients[client_id]['room_id']:
        room_id = test_meeting_room
        old_room = clients[client_id]['room_id']

        rooms[old_room] = [
            client for client in rooms[old_room]
            if client['client_id'] != user_name
        ]
        clients[client_id]['room_id'] = room_id

        rooms[room_id].append({'client_id': client_id, 'img_url': clients[user_name]['img_url']})
        print(f'{client_id}: {user_name} moved to room {room_id}')

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

    room_id = data.get('room_id')
    user_id = data.get('user_id')
    position_x = data.get('position_x')
    position_y = data.get('position_y')
    direction = data.get('direction') 

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
            'user_id': user_id,
            'position_x': position_x,
            'position_y': position_y,
            'direction': direction
        }, to=client['client_id'])

@sio_server.event
async def disconnect(sid):
    # 추후 Redis에서 데이터를 처리할 예정 {
    client_id = client_to_sid.get(sid)
    client_to_sid.pop(client_id)
    # }

    print(f'{client_id}:{sid}: disconnected')
