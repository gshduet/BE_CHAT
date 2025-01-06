import socketio
from urllib.parse import parse_qs
import asyncio

sio_server = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    cors_credentials=True,
)

sio_app = socketio.ASGIApp(socketio_server=sio_server, socketio_path="/sio/sockets")

# 방 정보를 관리하는 딕셔너리: {room_id: [client_id1, client_id2, ...]}
rooms = {}

# 클라이언트 정보를 관리하는 딕셔너리: {client_id: {...정보...}}
clients = {}

# client_id와 sid를 매핑하는 딕셔너리: {client_id: sid}
client_to_sid = {}

# 재접속을 대기하는 클라이언트 정보 관리: {client_id: {...정보...}}
disconnected_clients = {}
DISCONNECT_TIMEOUT = 2  # 재접속을 대기하는 최대 시간(초)

# 클라이언트 연결 이벤트 처리
@sio_server.event
async def connect(sid, environ):
    query_string = environ.get("QUERY_STRING", "")
    query_params = parse_qs(query_string)
    client_id = query_params.get("client_id", [None])[0]
    user_name = query_params.get("user_name", [None])[0]
    room_type = query_params.get("room_type", [None])[0]
    room_id = query_params.get("room_id", [None])[0]

    # 필수 데이터 유효성 검증
    if not client_id or not room_id:
        print(f"Connection rejected: client_id or room_id not provided")
        return False

    # 재접속 클라이언트 구분
    if client_id in disconnected_clients or client_id in clients.keys():
        reconnect_event = disconnected_clients[client_id].get("reconnect_event")
        reconnect_event.set()  # 재접속 이벤트 발생
        disconnected_clients.pop(client_id, None)

        # 기존 위치 데이터 유지
        client_data = clients.get(client_id, {})
        print(f"{user_name} ({client_id}): reconnected to room {room_id}")

    else:
        # 새로운 클라이언트 정보 초기화
        client_data = {
            "room_type": room_type,
            "room_id": room_id,
            "user_name": user_name,
            "position_x": 500,
            "position_y": 500,
            "direction": 1,
            "img_url": "img_url",
        }


        print(f"{user_name} ({client_id}): connected to room {room_id}")

    # 클라이언트 정보 출력
    print(f"{user_name} {client_data["user_name"]} {client_data["position_x"]} {client_data["position_y"]} {client_data["direction"]}")


    clients[client_id] = client_data
    client_to_sid[client_id] = sid

    if room_id not in rooms:
        rooms[room_id] = []
    if client_id not in rooms[room_id]:
        rooms[room_id].append(client_id)

    # 기존 클라이언트에게 새 클라이언트 정보 알림
    for client in rooms[room_id]:
        print(f"client: {clients[client]["user_name"]}")

        await sio_server.emit(
            "SC_MOVEMENT_INFO",
            {
                "client_id": client_id,
                "user_name": client_data["user_name"],
                "position_x": client_data["position_x"],
                "position_y": client_data["position_y"],
                "direction": client_data["direction"],
            },
            to=client_to_sid.get(client),
        )
        await sio_server.emit(
            "SC_ENTER_USER",
            {
                "client_id": client_id,
                "user_name": client_data["user_name"],
                "position_x": client_data["position_x"],
                "position_y": client_data["position_y"],
                "direction": client_data["direction"],
             },
            to=client_to_sid.get(client),
        )
        await sio_server.emit(
            "SC_ENTER_ROOM",
            {
                "user_id": client,
                "user_name": clients[client]["user_name"],
                "position_x": clients[client]["position_x"],
                "position_y": clients[client]["position_y"],
                "direction": clients[client]["direction"],
            },
            to=sid,
        )


@sio_server.event
async def CS_CHAT(sid, data):
    if not isinstance(data, dict):
        print(f"Error: Invalid data format")
        return

    # sid로 client_id 찾기
    client_id = None
    for cid, stored_sid in client_to_sid.items():
        if stored_sid == sid:
            client_id = cid
            break

    message = data.get("message")

    # 데이터 유효성 검증
    if not message or client_id not in clients.keys():
        print(f"Error: Missing fields or invalid client_id")
        return

    # 동일 방의 모든 클라이언트에게 메시지 전송
    room_id = clients[client_id]["room_id"]
    for client in rooms[room_id]:
        await sio_server.emit(
            "SC_CHAT",
            {"user_name": clients[client_id]["user_name"], "message": message},
            to=client_to_sid.get(client),
        )

    print(f"{clients[client_id]['user_name']} sent CS_CHAT {message}")

@sio_server.event
async def CS_PICTURE_INFO(sid, data):
    if not isinstance(data, dict):
        print("Error: Invalid data format")
        return

    # sid로 client_id 찾기
    client_id = None
    for cid, stored_sid in client_to_sid.items():
        if stored_sid == sid:
            client_id = cid
            break

    # 데이터 및 클라이언트 존재 여부 검증
    if not client_id or client_id not in clients.keys():
        print("Error: Invalid or missing client_id")
        return

    # 클라이언트가 속한 room_id 가져오기
    room_id = clients[client_id]["room_id"]

    # 방에 있는 모든 클라이언트에게 SC_PICTURE_INFO 전송
    for client in rooms[room_id]:
        await sio_server.emit(
            "SC_PICTURE_INFO",
            {
                "client_id": client_id,
                "data": data,  # 전달받은 데이터를 그대로 전송
            },
            to=client_to_sid.get(client),
        )

    print(f"{clients[client_id]['user_name']} sent CS_PICTURE_INFO to room {room_id}")

@sio_server.event
async def CS_MOVEMENT_INFO(sid, data):
    if not isinstance(data, dict):
        print(f"Error: Invalid data format")
        return

    # sid로 client_id 찾기
    client_id = None
    for cid, stored_sid in client_to_sid.items():
        if stored_sid == sid:
            client_id = cid
            break

    # 데이터 및 클라이언트 존재 여부 검증
    if not client_id or client_id not in clients.keys():
        print(f"Error: Invalid or missing client_id")
        return

    # 클라이언트 위치 정보 업데이트
    position_x = data.get("position_x")
    position_y = data.get("position_y")
    direction = data.get("direction", clients[client_id]["direction"])

    if position_x is None or position_y is None:
        print(f"Error: Missing position data")
        return

    clients[client_id].update({"position_x": position_x, "position_y": position_y, "direction": direction})

    print(f"{clients[client_id]['user_name']}: position ({position_x}, {position_y})")

    # 동일 방의 모든 클라이언트에게 움직임 정보 전송
    room_id = clients[client_id]["room_id"]
    for client in rooms[room_id]:
        await sio_server.emit(
            "SC_MOVEMENT_INFO",
            {
                "client_id": client_id,
                "user_name": clients[client_id]["user_name"],
                "position_x": position_x,
                "position_y": position_y,
                "direction": direction,
            },
            to=client_to_sid.get(client),
        )

@sio_server.event
async def disconnect(sid):
    client_id = None
    for cid, stored_sid in client_to_sid.items():
        if stored_sid == sid:
            client_id = cid
            break

    if client_id:
        client_to_sid.pop(client_id, None)
        room_id = clients[client_id]["room_id"]
        reconnect_event = asyncio.Event()
        disconnected_clients[client_id] = {
            "room_id": room_id,
            "position_x": clients[client_id]["position_x"],
            "position_y": clients[client_id]["position_y"],
            "direction": clients[client_id]["direction"],
            "reconnect_event": reconnect_event,
        }

        print(f"watching {client_id} for reconnection")

        try:
            await asyncio.wait_for(reconnect_event.wait(), timeout=DISCONNECT_TIMEOUT)
        except asyncio.TimeoutError:
            rooms[room_id].remove(client_id)
            # clients.pop(client_id, None)
            disconnected_clients.pop(client_id, None)

            for client in rooms[room_id]:
                await sio_server.emit(
                    "SC_LEAVE_USER",
                    {"client_id": client_id},
                    to=client_to_sid.get(client),
                )
            print(f"{client_id} disconnected completely from room {room_id}")