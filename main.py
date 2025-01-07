from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from sockets.sockets import sio_app, process_connection_queue
from core.redis import init_redis

app = FastAPI()
app.mount('/sio', app=sio_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # 서버 시작 시 Redis 초기화
    await init_redis()

    # 연결 요청 큐 처리
    asyncio.create_task(process_connection_queue())

@app.get("/")
async def home():
    return {"status": 200, "message": "my server is running"}


@app.get("/health")
async def health():
    return {"message": "OK"}
