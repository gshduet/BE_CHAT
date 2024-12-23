from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
from datetime import datetime

app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# {"room_id": str, "clients_id": list[str]}
rooms = {}
# 임시 데이터 초기화 -> memory DB로 대체 예정
rooms["floor7"] = ["user1", "user2"]
rooms["meetingroom_1"] = ["user3", "user4"]

class ConnectionManager:
    def __init__(self):
        # 클라이언트별로 웹소켓 연결을 관리하기 위한 딕셔너리
        # active_sessions: {"client_id":str, "websocket": WebSocket}
        self.active_sessions: dict[str, dict] = {}

    async def connect(self, client_id: str, room_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_sessions[client_id] = {"websocket": websocket, "room_id": room_id}
        if room_id not in rooms:
            rooms[room_id] = []
        rooms[room_id].append(client_id)

    def disconnect(self, client_id: str):
        if client_id in self.active_sessions:
            room_id = self.active_sessions[client_id]["room_id"]
            del self.active_sessions[client_id]
            if room_id in rooms and client_id in rooms[room_id]:
                rooms[room_id].remove(client_id)
                if not rooms[room_id]:  # 방에 사용자가 없으면 삭제
                    del rooms[room_id]

    async def broadcast(self, message: str):
        for client_id in self.active_sessions:
            await self.active_sessions[client_id]["websocket"].send_text(message)

    async def broadcast_to_room(self, room_id: str, message: str):
        if room_id in rooms:
            for client_id in rooms[room_id]:
                if client_id in self.active_sessions:
                    await self.active_sessions[client_id]["websocket"].send_text(message)

    async def change_room(self, client_id: str, new_room_id: str):
        if client_id in self.active_sessions:
            old_room_id = self.active_sessions[client_id]["room_id"]
            self.active_sessions[client_id]["room_id"] = new_room_id
            if old_room_id in rooms and client_id in rooms[old_room_id]:
                rooms[old_room_id].remove(client_id)
                if not rooms[old_room_id]:  # 이전 방이 비어 있으면 삭제
                    del rooms[old_room_id]
            if new_room_id not in rooms:
                rooms[new_room_id] = []
            rooms[new_room_id].append(client_id)

manager = ConnectionManager()

@app.websocket("/ws/{room_id}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_id: str):
    await manager.connect(client_id, room_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "CS_CHAT":
                await manager.broadcast_to_room(
                    room_id,
                    json.dumps({
                        "type": "SC_CHAT",
                        "room_id": room_id,
                        "user_name": client_id,
                        "chat_text": message["chat_text"],
                        "edit_at": datetime.now().isoformat()
                    })
                )
            elif message["type"] == "CHANGE_ROOM":          # 임시 방 변경 패킷
                new_room_id = message["new_room_id"]
                await manager.change_room(client_id, new_room_id)
                room_id = new_room_id  # 지역 변수 업데이트
            
            # 이후 다른 메시지 타입 추가 예정

    except WebSocketDisconnect:
        manager.disconnect(client_id)
