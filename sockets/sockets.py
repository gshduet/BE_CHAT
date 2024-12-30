import socketio
from urllib.parse import parse_qs
import asyncio

sio_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[]  # 특정 도메인 허용
)

sio_app = socketio.ASGIApp(
    socketio_server=sio_server,
    socketio_path='/sio/sockets'
)

# 추후 Redis를 사용하여 데이터를 저장할 예정 {
# 방 정보를 관리할 딕셔너리
# rooms = {room_id: [client_id1, client_id2]}
rooms = {}
default_room = "floor07"
test_meeting_room = "meeting_room"

# 클라이언트 정보를 저장할 딕셔너리
# clients = {client_id: {room_id: room_id, img_url: img_url}}
clients = {}

# sid와 client_id 매핑을 저장할 딕셔너리
client_to_sid = {}
# }

disconnected_clients = {}   # 재접속을 기다리는 클라이언트 정보를 저장할 딕셔너리
DISCONNECT_TIMEOUT = 5  # 5초 대기 후 disconnect 처리, 클라이언트의 재접속을 기다리는 시간

@sio_server.event
async def connect(sid, environ):
    # 클라이언트가 보낸 데이터에서 client_id 추출
    query_string = environ.get("QUERY_STRING", "")
    query_params = parse_qs(query_string)
    client_id = query_params.get("client_id", [None])[0]

    if not client_id:
        print(f"Connection rejected: client_id not provided")
        return False

    # 클라이언트가 재접속하는 경우 처리
    if client_id in disconnected_clients:
        print(f"Reconnecting client {client_id}")
        reconnect_event = disconnected_clients[client_id].get('reconnect_event')
        if reconnect_event:  # reconnect_event가 존재하는지 확인
            reconnect_event.set()
        disconnected_clients.pop(client_id, None)

    # 클라이언트 등록
    clients[client_id] = {
        'room_id': default_room,
        'img_url': 'img_url'
    }

    print(f'{client_id} ({sid}): connected')

    # 클라이언트 id와 sid 매핑
    client_to_sid[client_id] = sid

    # 중간 발표를 위한 테스트 코드
    # 클라이언트를 default_room에 추가
    if default_room not in rooms:
        rooms[default_room] = []

    if client_id not in rooms[default_room]:
        rooms[default_room].append(client_id)

    print(f'rooms: {rooms}')
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

    if client_id not in clients:
        print(f'Error: Client {client_id} does not exist.')
        return

    if room_id not in rooms:
        print(f'Error: Room {room_id} does not exist.')
        return

    print(f'{client_id}: {user_name} sent message: {message}')

    # 클라이언트가 방을 변경하는 경우
    # 자신의 room_id와 같은 메세지를 보내면 test_meeting_room으로 방을 변경
    if message == clients[client_id]['room_id']:
        old_room = clients[client_id]['room_id']
        clients[client_id]['room_id'] = test_meeting_room

        if old_room in rooms:
            rooms[old_room] = [client for client in rooms[old_room] if client != client_id]
        
        if test_meeting_room not in rooms:
            rooms[test_meeting_room] = []
        rooms[test_meeting_room].append(client_id)

        print(f'{client_id}: {user_name} moved to room {test_meeting_room}')

    # 해당 room에 있는 모든 클라이언트에게 메세지를 보냄
    for client in rooms[room_id]:
        await sio_server.emit('SC_CHAT', {
            'user_name': user_name,
            'message': message
        }, to=client_to_sid.get(client))

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
    
    print(f'user_id: {user_id}, room_id: {room_id}, position_x: {position_x}, position_y: {position_y}, direction: {direction}')

    # 해당 room에 있는 모든 클라이언트에게 움직임 정보를 전송
    for client in rooms[room_id]:
        await sio_server.emit('SC_MOVEMENT_INFO', {
            'user_id': user_id,
            'position_x': position_x,
            'position_y': position_y,
            'direction': direction
        }, to=client_to_sid.get(client))

@sio_server.event
async def disconnect(sid):
    client_id = None
    for cid, stored_sid in client_to_sid.items():
        if stored_sid == sid:
            client_id = cid
            break

    if client_id:
        client_to_sid.pop(client_id, None)
        room_id = clients[client_id]['room_id']

        # 클라이언트를 disconnected_clients 딕셔너리에 추가
        reconnect_event = asyncio.Event()
        disconnected_clients[client_id] = {
            'room_id': room_id,
            'reconnect_event': reconnect_event
        }

        print(f'{client_id}:{sid}: disconnected. Waiting for reconnect.')

        # 설정 시간동안 클라이언트의 재연결 대기.
        # 타임아웃이 지나면 클라이언트를 완전히 끊긴 것으로 처리함.
        try:
            await asyncio.wait_for(reconnect_event.wait(), timeout=DISCONNECT_TIMEOUT)
        except asyncio.TimeoutError:
            print(f'{client_id}: did not reconnect. Removing from server.')
            if room_id in rooms:
                rooms[room_id] = [client for client in rooms[room_id] if client != client_id]
            clients.pop(client_id, None)
            disconnected_clients.pop(client_id, None)

        print(f'rooms after disconnect: {rooms}')
