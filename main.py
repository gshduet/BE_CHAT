from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sockets.sockets import sio_app

app = FastAPI()
app.mount("/sio", app=sio_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jgtower.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def home():
    return {"status": 200, "message": "my server is running"}


@app.get("/health")
async def health():
    return {"message": "OK"}
