import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sockets.sockets import sio_app, init_redis

app = FastAPI()
app.mount('/sio', app=sio_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # 서버 시작 시 Redis 초기화
    await init_redis()

@app.get('/')
async def home():
    return {'message': 'my server is running'}


if __name__ == '__main__':
    uvicorn.run('main:app', port=8000, reload=True)
