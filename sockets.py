import socketio

sio_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[]
)

sio_app = socketio.ASGIApp(
    socketio_server=sio_server,
    socketio_path='sockets'
)

# 방 정보를 관리할 딕셔너리
# {"room_id": str, "clients": list[{clients_id, img_url}]}
rooms = {}
rooms['floor07'] = []
rooms['m'] = []

# 클라이언트 정보를 관리할 딕셔너리
# {"client_id": {"img_url": str, "room_id": str}}
clients = {}

@sio_server.event
async def connect(sid, environ):
    print(f'{sid}: connected')
    # 클라이언트가 connect하면 기본 룸 floor07에 join
    rooms['floor07'].append({'client_id': sid, 'img_url': "https://i.imgur"})
    clients[sid] = {'img_url': "https://i.imgur", 'room_id': 'floor07'}
    print(rooms)
    print(f'{sid}: joined floor07')
    
    await sio_server.emit('join', {'sid': sid})


@sio_server.event
async def CS_CHAT(sid, data):
    message = data.get('message')

    # 클라이언트가 m이라는 메세지를 보내면 해당 클라이언트의 rooms 정보를 m으로 변경
    # 이후에 이 부분은 api 서버에서 처리할 예정
    if message == 'm':
        room_id = clients[sid]['room_id']
        rooms[room_id] = [
            client for client in rooms[room_id] 
            if client['client_id'] != sid
        ]
        clients[sid]['room_id'] = 'm'
        rooms['m'].append({'client_id': sid, 'img_url': clients[sid]['img_url']})
        print(rooms)

        # 디버깅용 코드
        await sio_server.emit('SC_CHAT', 
                              {'sid': sid, 'message': "join m room"}, 
                              to=sid)

    else:
        # 이 클라이언트의 room 정보를 가져옴
        room = clients[sid]['room_id']
        # 해당 room에 있는 모든 클라이언트에게 메세지를 보냄
        for client in rooms[room]:
            await sio_server.emit('SC_CHAT', 
                                  {'sid': sid, 
                                   'message': message}, 
                                  to=client['client_id'])


@sio_server.event
async def disconnect(sid):
    # 클라이언트가 disconnect하면 해당 클라이언트의 room에서 제거
    room_id = clients[sid]['room_id']
    rooms[room_id] = [
        client for client in rooms[room_id] 
        if client['client_id'] != sid
    ]
    clients.pop(sid, None)
    print(f'{sid}: disconnected')
