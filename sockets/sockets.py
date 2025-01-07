import socketio
from urllib.parse import parse_qs
import asyncio
from core.databases import get_redis

from core.redis import (
    add_to_room,
    remove_from_room,
    get_room_clients,
    set_client_info,
    get_client_info,
    delete_client_info,
    set_sid_mapping,
    get_client_id_by_sid,
    delete_sid_mapping,
    get_sid_by_client_id,
    set_disconnected_client,
    get_disconnected_client,
    delete_disconnected_client,
)

sio_server = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    cors_credentials=True,
    ping_timeout=20,  # 클라이언트 응답 대기
    ping_interval=25,  # Ping 메시지 전송 간격
)

DISCONNECT_TIMEOUT = 3

sio_app = socketio.ASGIApp(socketio_server=sio_server, socketio_path="/sio/sockets")


# 클라이언트 연결 이벤트 처리
@sio_server.event
async def connect(sid, environ):
    query_string = environ.get("QUERY_STRING", "")
    query_params = parse_qs(query_string)
    client_id = query_params.get("client_id", [None])[0]
    user_name = query_params.get("user_name", [None])[0]
    room_id = query_params.get("room_id", [None])[0]

    if not client_id or not room_id:
        return False

    async for redis_client in get_redis():
        # 재접속 클라이언트 처리
        disconnected_client = await get_disconnected_client(client_id, redis_client)
        if disconnected_client:
            await delete_disconnected_client(client_id, redis_client)
            await set_client_info(client_id, disconnected_client, redis_client)
            await set_sid_mapping(client_id, sid, redis_client)
            await add_to_room(room_id, client_id, redis_client)

            print(f"{user_name} ({client_id}) reconnected to room {room_id}")

        else:
            client_data = {
                "room_id": room_id,
                "user_name": user_name,
                "position_x": 500,
                "position_y": 500,
                "direction": 1,
            }

            await set_client_info(client_id, client_data, redis_client)
            await set_sid_mapping(client_id, sid, redis_client)
            await add_to_room(room_id, client_id, redis_client)

            print(f"{user_name} ({client_id}) connected to room {room_id}")


# 같은 방에 있는 클라이언트들의 정보를 모두 전송(본인 정보 포함)
@sio_server.event
async def CS_USER_POSITION_INFO(sid, data):
    async for redis_client in get_redis():
        new_client_id = await get_client_id_by_sid(sid, redis_client)
        if not new_client_id:
            print(f"Error: SID {sid} not mapped to any client ID.")
            return

        new_client_info = await get_client_info(new_client_id, redis_client)
        room_id = new_client_info.get("room_id")

        for client in await get_room_clients(room_id, redis_client):
            client_info = await get_client_info(client, redis_client)
            if not client_info:
                continue

            # 기존 클라이언트에게 새로운 클라이언트 정보 전송
            client_sid = await get_sid_by_client_id(client, redis_client)
            await sio_server.emit(
                "SC_USER_POSITION_INFO",
                {
                    "client_id": new_client_id,
                    "user_name": new_client_info.get("user_name", "Unknown"),
                    "position_x": int(new_client_info.get("position_x")),
                    "position_y": int(new_client_info.get("position_y")),
                    "direction": int(new_client_info.get("direction")),
                },
                to=client_sid,
            )

            # 새로운 클라이언트에게 기존 클라이언트 정보 전송
            await sio_server.emit(
                "SC_USER_POSITION_INFO",
                {
                    "client_id": client,
                    "user_name": client_info.get("user_name", "Unknown"),
                    "position_x": int(client_info.get("position_x")),
                    "position_y": int(client_info.get("position_y")),
                    "direction": int(client_info.get("direction")),
                },
                to=sid,
            )


@sio_server.event
async def CS_LEAVE_USER(sid, data):
    async for redis_client in get_redis():
        # sid로 client_id 찾기
        client_id = await get_client_id_by_sid(sid, redis_client)

        if not client_id:
            return

        client_info = await get_client_info(client_id, redis_client)
        room_id = client_info.get("room_id")

        # 방에 있는 모든 클라이언트에게 퇴장 정보 전송(본인 포함)
        for client in await get_room_clients(room_id, redis_client):
            client_sid = await get_sid_by_client_id(client, redis_client)
            await sio_server.emit(
                "SC_LEAVE_USER",
                {"client_id": client_id},
                to=client_sid,
            )

        # 해당 룸에서 클라이언트 제거
        await remove_from_room(room_id, client_id, redis_client)

        print(f"{client_info.get('user_name')} left room {room_id}")


@sio_server.event
async def CS_CHAT(sid, data):
    if not isinstance(data, dict):
        print(f"Error: Invalid data format")
        return

    async for redis_client in get_redis():
        # sid로 client_id 찾기
        client_id = await get_client_id_by_sid(sid, redis_client)
        if not client_id:
            print("Error: Invalid or missing client_id")
            return

        # 클라이언트 정보 가져오기
        client_info = await get_client_info(client_id, redis_client)
        if not client_info:
            print(f"Error: Missing client_info for client_id {client_id}")
            return

        user_name = client_info.get("user_name")
        room_id = client_info.get("room_id")

        message = data.get("message")

        if not message:
            print("Error: Missing message data")
            return

        # 방에 있는 모든 클라이언트에게 메시지 전송
        for client in await get_room_clients(room_id, redis_client):
            if client == client_id:
                continue

            client_sid = await get_sid_by_client_id(client, redis_client)
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


@sio_server.event
async def CS_PICTURE_INFO(sid, data):
    if not isinstance(data, dict):
        print("Error: Invalid data format")
        return

    async for redis_client in get_redis():
        # sid로 client_id 찾기
        client_id = await get_client_id_by_sid(sid, redis_client)
        if not client_id:
            print("Error: Invalid or missing client_id")
            return

        # 클라이언트 정보 가져오기
        client_info = await get_client_info(client_id, redis_client)
        if not client_info:
            print(f"Error: Missing client_info for client_id {client_id}")
            return

        # 클라이언트가 속한 room_id 가져오기
        room_id = client_info.get("room_id")

        print(f"{client_info['user_name']} sent CS_PICTURE_INFO to room {room_id}")

        # 방에 있는 모든 클라이언트에게 SC_PICTURE_INFO 전송
        for client in await get_room_clients(room_id, redis_client):
            client_sid = await get_sid_by_client_id(client, redis_client)
            await sio_server.emit(
                "SC_PICTURE_INFO",
                {
                    "client_id": client_id,
                    "user_name": client_info.get("user_name"),
                    "picture": data.get("picture"),
                },
                to=client_sid,
            )

            # 받은 사람 정보 출력
            print(f"SC_PICTURE_INFO sent to {client}")


@sio_server.event
async def CS_MOVEMENT_INFO(sid, data):
    if not isinstance(data, dict):
        print("Error: Invalid data format")
        return

    async for redis_client in get_redis():
        # sid로 client_id 찾기
        client_id = await get_client_id_by_sid(sid, redis_client)
        if not client_id:
            print("Error: Invalid or missing client_id")
            return

        # 클라이언트 정보 가져오기
        client_info = await get_client_info(client_id, redis_client)
        if not client_info:
            print(f"Error: Missing client_info for client_id {client_id}")
            return

        user_name = client_info.get("user_name")

        # 위치 데이터 업데이트
        position_x = data.get("position_x")
        position_y = data.get("position_y")
        direction = data.get("direction")

        if position_x is None or position_y is None:
            print("Error: Missing position data")
            return

        # Redis에 업데이트된 정보 저장
        client_info.update(
            {"position_x": position_x, "position_y": position_y, "direction": direction}
        )
        await set_client_info(client_id, client_info, redis_client)

        print(f"{client_info['user_name']}:({position_x}, {position_y})")

        # 동일 방의 모든 클라이언트에게 움직임 정보 전송
        room_id = client_info.get("room_id")
        if not room_id:
            print(f"Error: Missing room_id for client_id {client_id}")
            return

        for client in await get_room_clients(room_id, redis_client):
            client_sid = await get_sid_by_client_id(client, redis_client)
            await sio_server.emit(
                "SC_MOVEMENT_INFO",
                {
                    "client_id": client_id,
                    "user_name": user_name,
                    "position_x": position_x,
                    "position_y": position_y,
                    "direction": direction,
                },
                to=client_sid,
            )


@sio_server.event
async def disconnect(sid):
    async for redis_client in get_redis():
        client_id = await get_client_id_by_sid(sid, redis_client)
        if not client_id:
            return

        client_data = await get_client_info(client_id, redis_client)
        if not client_data:
            print(f"Error: No client data for SID {sid}")
            return

        room_id = client_data.get("room_id")

        reconnect_event = asyncio.Event()
        print(f"watching {client_id} for reconnection")

        # 재접속 대기 클라이언트로 이동
        await set_disconnected_client(client_id, client_data, redis_client)
        try:
            await asyncio.wait_for(reconnect_event.wait(), timeout=DISCONNECT_TIMEOUT)
        except asyncio.TimeoutError:
            await delete_sid_mapping(sid, redis_client)
            await delete_client_info(client_id, redis_client)
            await remove_from_room(room_id, client_id, redis_client)

            # 방에 남은 클라이언트에게 퇴장 정보 전송
            for client in await get_room_clients(room_id, redis_client):
                client_sid = await get_sid_by_client_id(client, redis_client)
                await sio_server.emit(
                    "SC_LEAVE_USER",
                    {"client_id": client_id},
                    to=client_sid,
                )

            print(f"{client_id} disconnected from room {room_id}")
