import socketio
from urllib.parse import parse_qs
from core.redis import redis_client
from core.redis import (
    add_to_room, remove_from_room, get_room_clients,
    set_client_info, get_client_info, delete_client_info,
    set_sid_mapping, get_client_id_by_sid, delete_sid_mapping
)

sio_server = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    cors_credentials=True,
)

sio_app = socketio.ASGIApp(socketio_server=sio_server, socketio_path="/sio/sockets")

# 클라이언트 연결 이벤트 처리
@sio_server.event
async def connect(sid, environ):
    # Query string에서 클라이언트 정보 파싱
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

    # Redis에 클라이언트 정보 저장
    client_info = {
        "room_type": room_type,
        "room_id": room_id,
        "user_name": user_name,
        "position_x": 500,  # 기본 위치
        "position_y": 500,  # 기본 위치
        "direction": 1,    # 기본 방향
        "img_url": "img_url",  # 기본 이미지 URL
    }
    await set_client_info(client_id, client_info)
    await set_sid_mapping(client_id, sid)
    await add_to_room(room_id, client_id)

    # 동일 방의 모든 클라이언트에게 이동 정보 전송
    room_id = client_info["room_id"]
    clients_in_room = await get_room_clients(room_id)
    for client in clients_in_room:
        await sio_server.emit(
            "SC_MOVEMENT_INFO",
            {
                "client_id": client_id,
                "user_name": client_info["user_name"],
                "position_x": client_info["position_x"],
                "position_y": client_info["position_y"],
                "direction": client_info["direction"],
            },
            to=await get_client_id_by_sid(client)
        )

    print(f"{user_name} ({client_id}): connected to room {room_id}")

# 클라이언트 메시지 처리
@sio_server.event
async def CS_CHAT(sid, data):
    # sid로 client_id 찾기
    client_id = await get_client_id_by_sid(sid)
    if not client_id:
        print("Error: Invalid sid")
        return

    message = data.get("message")
    if not message:
        print("Error: Missing message")
        return

    # 방에 있는 모든 클라이언트에게 메시지 전송
    room_id = (await get_client_info(client_id)).get("room_id")
    clients_in_room = await get_room_clients(room_id)
    for client in clients_in_room:
        client_info = await get_client_info(client)
        await sio_server.emit(
            "SC_CHAT",
            {"user_name": client_info["user_name"], "message": message},
            to=await get_client_id_by_sid(client)
        )

    print(f"{client_id} sent a message: {message}")

# 클라이언트 이동 정보 처리
@sio_server.event
async def CS_MOVEMENT_INFO(sid, data):
    # sid로 client_id 찾기
    client_id = await get_client_id_by_sid(sid)
    if not client_id:
        print("Error: Invalid sid")
        return

    # 이동 데이터 가져오기
    position_x = data.get("position_x")
    position_y = data.get("position_y")
    direction = data.get("direction")

    if position_x is None or position_y is None:
        print("Error: Missing position data")
        return

    # Redis에 클라이언트 위치 정보 업데이트
    client_info = await get_client_info(client_id)
    client_info.update({"position_x": position_x, "position_y": position_y, "direction": direction})
    await set_client_info(client_id, client_info)

    # 동일 방의 모든 클라이언트에게 이동 정보 전송
    room_id = client_info["room_id"]
    clients_in_room = await get_room_clients(room_id)
    for client in clients_in_room:
        await sio_server.emit(
            "SC_MOVEMENT_INFO",
            {
                "client_id": client_id,
                "user_name": client_info["user_name"],
                "position_x": position_x,
                "position_y": position_y,
                "direction": direction,
            },
            to=await get_client_id_by_sid(client)
        )

    print(f"{client_id} moved to ({position_x}, {position_y})")

# 클라이언트 연결 해제 처리
@sio_server.event
async def disconnect(sid):
    # sid로 client_id 찾기
    client_id = await get_client_id_by_sid(sid)
    if not client_id:
        print("Error: Invalid sid")
        return

    # Redis에서 클라이언트 정보 가져오기
    client_info = await get_client_info(client_id)
    if not client_info or "room_id" not in client_info:
        print(f"Error: Client info not found or missing room_id for client_id {client_id}")
        await delete_sid_mapping(sid)
        return

    room_id = client_info["room_id"]

    # Redis에서 클라이언트 정보 삭제
    await delete_sid_mapping(sid)
    await remove_from_room(room_id, client_id)
    await delete_client_info(client_id)

    # 방에 남은 클라이언트에게 퇴장 정보 전송
    clients_in_room = await get_room_clients(room_id)
    for client in clients_in_room:
        await sio_server.emit(
            "SC_LEAVE_USER",
            {"client_id": client_id},
            to=await get_client_id_by_sid(client)
        )

    print(f"{client_id} disconnected completely from room {room_id}")

