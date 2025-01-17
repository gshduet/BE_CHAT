from typing import List, Dict

# SectorManager 클래스: 클라이언트의 위치를 기반으로 섹터를 관리하는 클래스
# 섹터 크기를 설정하고 클라이언트를 섹터에 추가하거나 인접한 섹터의 클라이언트를 반환합니다.
class SectorManager:
    def __init__(self, sector_size: int):
        self.sector_size = sector_size
        self.sectors: Dict[str, List[str]] = {}

    # 주어진 좌표를 기반으로 섹터 키를 반환
    def get_sector_key(self, x: int, y: int) -> str:
        return f"{int(x) // self.sector_size}:{int(y) // self.sector_size}"

    # 클라이언트의 섹터 위치를 업데이트
    def update_client_sector(self, client_id: str, x: int, y: int):
        key = self.get_sector_key(x, y)
        for sector, clients in self.sectors.items():
            if client_id in clients and sector != key:
                clients.remove(client_id)
        self.sectors.setdefault(key, []).append(client_id)

    # 인접 섹터에 있는 클라이언트 목록을 반환
    def get_nearby_clients(self, x: int, y: int) -> List[str]:
        sector_key = self.get_sector_key(x, y)
        nearby = set()
        for offset_x in [-1, 0, 1]:
            for offset_y in [-1, 0, 1]:
                nearby_sector = f"{x // self.sector_size + offset_x}:{y // self.sector_size + offset_y}"
                nearby.update(self.sectors.get(nearby_sector, []))
        return list(nearby)

# SectorManager 인스턴스 생성
# 임시 섹터 크기 100으로 설정
sector_manager = SectorManager(sector_size=300)

# 클라이언트의 view list
client_view_list = {}

# 클라이언트의 이동을 처리하는 함수
# 클라이언트의 새 위치를 업데이트
# 섹터 정보를 기반으로 인접 클라이언트에게 이동 정보를 전송
async def update_movement(sid, data, emit_callback):
    client_id = data.get("client_id")
    if not client_id:
        print("Client ID missing")
        return

    user_name = data.get("user_name")

    # 클라이언트의 새 위치와 방향 정보 가져오기
    x, y, direction = int(data.get("position_x")), int(data.get("position_y")), data.get("direction")
    if x is None or y is None:
        print("Missing position data")
        return

    # 섹터 정보를 업데이트하고 인접 클라이언트를 가져오기
    sector_manager.update_client_sector(client_id, x, y)
    nearby_clients = sector_manager.get_nearby_clients(x, y)

    # 인접 클라이언트에게 이동 정보 전송
    for other_client in nearby_clients:
        if other_client == client_id:
            continue

        await emit_callback(other_client, {
            "client_id": client_id,
            "position_x": int(x),
            "position_y": int(y),
            "direction": int(direction),
            "user_name": user_name,
        })

    # print(f"Client {client_info.get('user_name')} move to ({x}, {y})")

# 클라이언트의 시야 목록을 업데이트하는 함수
# 새롭게 보이는 클라이언트를 추가하고 보이지 않게 된 클라이언트를 제거
async def handle_view_list_update(sid, data, emit_callback, client_info_store):
    client_id = data.get("client_id")
    if not client_id:
        print("Client ID missing")
        return
    
    # 키가 없으면 빈 리스트로 초기화
    if client_id not in client_view_list:
        client_view_list[client_id] = []

    # 현재 위치를 기준으로 새로운 시야 목록 계산
    new_view_list = sector_manager.get_nearby_clients(
        data.get("position_x"), data.get("position_y")
    )

    # 기존 시야 목록 가져오기
    current_view_list = client_view_list.get(client_id, [])

    # 현재 시야 목록과 비교하여 추가 및 제거할 클라이언트 계산
    added_clients = set(new_view_list) - set(current_view_list)

    # 새롭게 보이는 클라이언트를 클라이언트에게 전송
    for client in added_clients:
        if client not in client_info_store:
            continue

        client_data = client_info_store[client]
        await emit_callback(client, {
            "client_id": client,
            "user_name": client_data.user_name,
            "position_x": int(client_data.position_x),
            "position_y": int(client_data.position_y),
            "direction": int(client_data.direction),
        })

    # 시야 목록 업데이트
    client_view_list[client_id] = new_view_list
