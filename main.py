from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from sockets.sockets import sio_app, process_connection_requests

app = FastAPI()
app.mount("/sio", app=sio_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(process_connection_requests())

@app.get("/health")
async def health():
    return {"message": "OK"}


@app.get("/")
async def home():
    return {"status": 200, "message": "my server is running"}
