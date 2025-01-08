from typing import Generator, AsyncGenerator
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError
from sqlmodel import Session, create_engine
from core.config import settings
import asyncio

engine = create_engine(
    settings.db_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)

# Redis 연결 풀 설정
redis_pool = ConnectionPool(
    host=settings.aws_elasticache_endpoint,
    port=settings.aws_elasticache_port,
    decode_responses=True,
    socket_timeout=settings.redis_socket_timeout,
    socket_connect_timeout=settings.redis_socket_connect_timeout,
    retry_on_timeout=settings.redis_retry_on_timeout,
    max_connections=settings.redis_max_connections,
    health_check_interval=30,
)

# Redis 클라이언트 인스턴스 생성
redis_client = Redis(
    connection_pool=redis_pool,
    auto_close_connection_pool=True,
)


def get_db() -> Generator[Session, None, None]:
    """
    SQLAlchemy 엔진을 사용하여 데이터베이스 세션을 생성하고 반환합니다.
    이 함수는 FastAPI의 Depends 의존성 주입 시스템에서 사용되며, 데이터베이스 세션을 제공하는 데 사용됩니다.
    """
    with Session(engine) as session:
        yield session


MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Redis 클라이언트를 반환하는 비동기 의존성 주입 함수입니다.
    이 함수는 FastAPI의 Depends 의존성 주입 시스템에서 사용되며, Redis 클라이언트를 제공하는 데 사용됩니다.
    연결 실패 시 최대 3번까지 재시도하며, 각 시도 사이에 1초의 대기 시간을 가집니다.
    """
    retries = 0
    last_error = None

    while retries < MAX_RETRIES:
        try:
            # Redis 연결 상태 확인
            await redis_client.ping()
            yield redis_client
            return
        except (RedisError, ConnectionError) as e:
            last_error = e
            retries += 1
            if retries < MAX_RETRIES:
                print(
                    f"Redis connection failed: {e}. Retrying... (attempt {retries}/{MAX_RETRIES})"
                )
                await asyncio.sleep(RETRY_DELAY)
            else:
                print(
                    f"Redis connection failed after {MAX_RETRIES} attempts: {last_error}"
                )
                raise last_error
        finally:
            # 연결 풀은 유지하되 현재 연결은 닫음
            await redis_client.close(close_connection_pool=False)
