'''
소켓으로 캐릭터의 이동을 받아, 브로드캐스팅 하는 코드
    1. 소켓으로 받은 데이터를 어떻게 처리할 것인지
    2. 브로드캐스팅을 어떻게 할 것인지
    3. 브로드캐스팅을 어디에 할 것인지
    4. 브로드캐스팅을 어떤 조건으로 할 것인지
    5. 브로드캐스팅을 어떤 데이터로 할 것인지
        5.1 데이터를 패킷으로 관리하장
----------------------------------------------
7층에 있는 사람에게만 보낼 것인지?
    1. 프론트에 일단 다 보내고 프론트에서 마이룸, 미팅룸에 있는 사람들에게는 그리지 않을 것인지
    2. 백에서 조건 체크 하여 정제해 보낼 것인지
        2.1 메모리DB를 히트하여 7층 리스트에만 브로드 캐스트
            2.1.1 메모리DB 리스트를 어케 디자인 할건데
                2.1.1.1 7층 메인페이지 리스트, 마이룸 리스트, 미팅룸 리스트
                2.1.1.2 유저가 가지고 있을 정보는?
                    2.1.1.2.1 소켓 정보, 이름, 위치(x,y), 방 정보(메인페이지, 마이룸, 미팅룸(번호도 같이))
'''

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
# import asyncio
import json

app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 예시 {"type": "chat", "content": "Hello, world!"}
            # 예시 {"type": "movement", "position": {"x": 0, "y": 0}}
            # 이 부분이 패킷의 타입을 구분하는 부분!
            if message["type"] == "chat":
                await manager.broadcast(json.dumps({"type": "chat", "content": message["content"]}))
            elif message["type"] == "movement":
                await manager.broadcast(json.dumps({"type": "movement", "position": message["position"]}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
