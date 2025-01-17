import socketio
from urllib.parse import parse_qs
import asyncio
from core.databases import get_redis

from core.redis import (
    add_to_room,
    remove_from_room,
    get_room_clients,
    set_disconnected_client,
    get_disconnected_client,
    delete_disconnected_client,
    enqueue_connection_request,
    dequeue_connection_request,
)

from core.movement import update_movement, handle_view_list_update, sector_manager


sio_server = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    cors_credentials=True,
    ping_timeout=20,  # 클라이언트 응답 대기
    ping_interval=25,  # Ping 메시지 전송 간격
)

sio_app = socketio.ASGIApp(socketio_server=sio_server, socketio_path="/sio/sockets")

class client_info:
    def __init__(self, sid):
        self.client_id = None
        self.user_name = None
        self.position_x = None
        self.position_y = None
        self.direction = None
        self.room_type = None
        self.room_id = None
        self.sid = sid


# 이벤트 객체를 저장할 전역 딕셔너리
asyncio_event_store = {}

# 클라이언트 정보를 저장할 전역 딕셔너리
client_info_store = {}

# 클라이언트의 view list
client_view_list = {}

# sid로 클라이언트 아이디 찾기
def find_key_by_sid(sid_to_find):
    for key, value in client_info_store.items():
        if value.sid == sid_to_find:
            return key
    return None

# 클라이언트의 정보가 있는지 확인
def client_in_client_data_store(key):
    return key in client_info_store

# redis 큐에서서 연결 요청 처리
async def process_connection_requests():
    async for redis_client in get_redis():
        while True:
            request = await dequeue_connection_request(redis_client)
            if request:
                sid = request["sid"]
                client_id = request["client_id"]
                user_name = request["user_name"]

                # 클라이언트 아이디가 재접속 리스트에 있는지 확인
                client_data = await get_disconnected_client(client_id, redis_client)
                if client_data:
                    # 재접속 처리
                    client_data = {
                        "user_name": user_name,
                        "position_x": client_data.get("position_x"),
                        "position_y": client_data.get("position_y"),
                        "direction": client_data.get("direction"),
                    }
                    await delete_disconnected_client(client_id, redis_client)
                    print(f"Reconnection client: {client_id}")

                else:
                    client_data = {
                        "user_name": user_name,
                        "position_x": 350,
                        "position_y": 170,
                        "direction": 1,
                    }
                    print(f"New connection: sid:{sid}, client_id:{client_id}")
                
                client_info_store[client_id].user_name = user_name
                client_info_store[client_id].position_x = client_data.get("position_x")
                client_info_store[client_id].position_y = client_data.get("position_y")
                client_info_store[client_id].direction = client_data.get("direction")
                print(f"process_connection_requests {user_name}")

                # 이벤트 객체 완료 알림
                event = asyncio_event_store.pop(sid, None)
                if event:
                    event.set()
                    print(f"Event for SID {sid} set.")

            await asyncio.sleep(0.1)


# 클라이언트 연결 이벤트 처리
@sio_server.event
async def connect(sid, environ):
    query_string = environ.get("QUERY_STRING", "")
    query_params = parse_qs(query_string)
    client_id = query_params.get("client_id", [None])[0]
    user_name = query_params.get("user_name", [None])[0]

    if not client_id:
        return False
    
    # 해당 client_id가 매핑된 sid가 있는지 확인
    async for redis_client in get_redis():
        if client_id in client_info_store:
            # 중복 연결 아이디면 기존 연결 끊기
            old_sid = client_info_store[client_id].sid
            if old_sid:
                await sio_server.emit(
                    "SC_DUPLICATE_CONNECTION",
                    {"message": "Duplicate connection detected."},
                    to=old_sid,
                )
            client_info_store[client_id].sid = sid
            await sio_server.disconnect(old_sid)
        else:
            client_info_store[client_id] = client_info(sid)
            
        event = asyncio.Event()
        await enqueue_connection_request(redis_client, sid, client_id, user_name)

        # 이벤트 객체를 전역 딕셔너리에 저장
        asyncio_event_store[sid] = event
        print(f"enqueued: sid:{sid}, client_id:{client_id}")

        # 연결 요청 완료 대기
        while asyncio_event_store.get(sid):
            await event.wait()
            print(f"Event for SID {sid} completed.")
        print(f"Connection completed: sid:{sid}, client_id:{client_id}")

@sio_server.event
async def CS_JOIN_ROOM(sid, data):
    client_id = data.get("client_id")
    room_type = data.get("room_type")
    room_id = data.get("room_id")

    if not client_id or not room_type or not room_id:
        print("Error: Missing required data0")
        return

    async for redis_client in get_redis():
        # 클라이언트 정보 업데이트 room_type, room_id
        client_info_store[client_id].room_type = room_type
        client_info_store[client_id].room_id = room_id
        
        # 방에 클라이언트 추가
        await add_to_room(room_id, client_id, redis_client)


@sio_server.event
async def CS_USER_POSITION(sid, data):
    client_id = data.get("client_id")
    room_id = data.get("room_id")

    if not client_id or not room_id:
        print("Error: Missing required data1")
        return

    async for redis_client in get_redis():
        await sio_server.emit(
            "SC_USER_POSITION_INFO",
            {
                "client_id": client_id,
                "user_name": client_info_store[client_id].user_name,
                "position_x": int(float(client_info_store[client_id].position_x)),
                "position_y": int(float(client_info_store[client_id].position_y)),
                "direction": int(float(client_info_store[client_id].direction)),
            },
            to=sid,
        )
    
        for client in await get_room_clients(room_id, redis_client):
            if client_id != client:
                # 기존 클라이언트에게 새로운 클라이언트 정보 전송
                client_sid = client_info_store[client].sid
                
                await sio_server.emit(
                    "SC_USER_POSITION_INFO",
                    {
                        "client_id": client_id,
                        "user_name": client_info_store[client_id].user_name,
                        "position_x": int(float(client_info_store[client_id].position_x)),
                        "position_y": int(float(client_info_store[client_id].position_y)),
                        "direction": int(float(client_info_store[client_id].direction)),
                    },
                    to=client_sid,
                )

           
            # 새로운 클라이언트에게 기존 클라이언트 정보 전송
                await sio_server.emit(
                    "SC_USER_POSITION_INFO",
                    {
                        "client_id": client,
                        "user_name": client_info_store[client].user_name,
                        "position_x": int(float(client_info_store[client].position_x)),
                        "position_y": int(float(client_info_store[client].position_y)),
                        "direction": int(float(client_info_store[client].direction)),
                    },
                    to=sid,
                )


@sio_server.event
async def CS_LEAVE_ROOM(sid, data):
    client_id = data.get("client_id")
    room_id = data.get("room_id")

    if not client_id or not room_id:
        print("Error: Missing required data2")
        return

    async for redis_client in get_redis():
        # 방에서 클라이언트 제거
        await remove_from_room(room_id, client_id, redis_client)

        # 방에 있는 모든 클라이언트에게 퇴장 정보 전송(본인 포함)
        for client in await get_room_clients(room_id, redis_client):
            client_sid = client_info_store[client].sid
            await sio_server.emit(
                "SC_LEAVE_ROOM",
                {"client_id": client_id},
                to=client_sid,
            )

        print(f"{client_id} left room {room_id}")



@sio_server.event
async def CS_CHAT(sid, data):
    client_id = data.get("client_id")

    if not client_id:
        print("Error: Missing required data4")
        return

    async for redis_client in get_redis():
        # 클라이언트 정보 가져오기
        user_name = client_info_store[client_id].user_name
        room_id = client_info_store[client_id].room_id

        message = data.get("message")

        if not message:
            print("Error: Missing message data")
            return

        # 방에 있는 모든 클라이언트에게 메시지 전송
        for client in await get_room_clients(room_id, redis_client):
            client_sid = client_info_store[client].sid
            await sio_server.emit(
                "SC_CHAT",
                {
                    "user_name": user_name,
                    "message": message,
                },
                to=client_sid,
            )

            print(f"sent to {client}")

        print(f"{user_name} sent message : {message}")

# 미팅룸 그림판 정보 관련 이벤트
@sio_server.event
async def CS_PICTURE_INFO(sid, data):
    if not isinstance(data, dict):
        print("Error: Invalid data format")
        return
    
    client_id = data.get("client_id")

    if not client_id:
        print("Error: Missing required data5")
        return

    async for redis_client in get_redis():
        # 클라이언트가 속한 room_id 가져오기
        room_id = client_info_store[client_id].room_id
        user_name = client_info_store[client_id].user_name


        print(f"{user_name} sent CS_PICTURE_INFO to room {room_id}")

        # 방에 있는 모든 클라이언트에게 SC_PICTURE_INFO 전송
        for client in await get_room_clients(room_id, redis_client):
            if client == client_id:
                continue

            client_sid = client_info_store[client].sid
            await sio_server.emit(
                "SC_PICTURE_INFO",
                {
                    "client_id": client_id,
                    "user_name": user_name,
                    "picture": data.get("picture"),
                },
                to=client_sid,
            )


@sio_server.event
async def CS_MOVEMENT_INFO(sid, data):
    if not isinstance(data, dict):
        print("Error: Invalid data format")
        return

    client_id = data.get("client_id")
    if not client_id:
        print("Error: Missing required data")
        return

    if client_id not in client_info_store:
        print(f"Error: Client {client_id} not found in client_info_store")
        return

    client_info_store[client_id].position_x = data.get("position_x")
    client_info_store[client_id].position_y = data.get("position_y")
    client_info_store[client_id].direction = data.get("direction")

    await handle_view_list_update(
        sid=sid,
        data=data,
        emit_callback=emit_to_client,
        client_info_store=client_info_store,
        client_view_list=client_view_list
    )
    await update_movement(
        sid=sid,
        data=data,
        emit_callback=emit_to_client,
        client_info_store=client_info_store
    )

async def emit_to_client(target_client, packet):
    if target_client not in client_info_store:
        print(f"Error: Target client {target_client} not found in client_info_store")
        return

    client_sid = client_info_store[target_client].sid
    if client_sid:
        await sio_server.emit("SC_MOVEMENT_INFO", packet, to=client_sid)

@sio_server.event
async def disconnect(sid):
    async for redis_client in get_redis():
        try:
            client_id = find_key_by_sid(sid)
            if not client_id:
                print(f"No client_id mapped for SID {sid}")
                return

            room_id = client_info_store[client_id].room_id

            print(f"watching {client_id} for reconnection")

            # 클라이언트 정보 삭제
            await remove_from_room(room_id, client_id, redis_client)

            # 방에 있는 모든 클라이언트에게 퇴장 정보 전송
            for client in await get_room_clients(room_id, redis_client):
                client_sid = client_info_store[client].sid
                if client_sid:
                    await sio_server.emit(
                        "SC_LEAVE_USER",
                        {"client_id": client_id},
                        to=client_sid,
                    )

                    await sio_server.emit(
                        "SC_LEAVE_ROOM",
                        {"client_id": client_id},
                        to=client_sid,
                    )

            disconnected_client_data = {
                "client_id": client_id,
                "user_name": client_info_store[client_id].user_name,
                "position_x": client_info_store[client_id].position_x,
                "position_y": client_info_store[client_id].position_y,
                "direction": client_info_store[client_id].direction,
            }

            await set_disconnected_client(client_id, disconnected_client_data, redis_client)
            client_info_store.pop(client_id)

            # client_view_list에서 클라이언트 삭제
            if client_id in client_view_list:
                client_view_list.pop(client_id)

            # client_view_list 값에서 클라이언트 제거
            for key, value in client_view_list.items():
                if client_id in value:
                    value.remove(client_id)

            # 섹터에서 클라이언트 제거
            sector_manager.remove_client_from_sector(client_id)

        except Exception as e:
            print(f"Disconnect handler error: {e}")



