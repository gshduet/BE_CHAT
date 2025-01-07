from typing import Generator, AsyncGenerator

from redis.asyncio import Redis
from sqlmodel import Session, create_engine

from core.config import settings


engine = create_engine(
    settings.db_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)

redis_client = Redis(
    host=settings.aws_elasticache_endpoint,
    port=settings.aws_elasticache_port,
    decode_responses=True,
    socket_timeout=settings.redis_socket_timeout,
    socket_connect_timeout=settings.redis_socket_connect_timeout,
    retry_on_timeout=settings.redis_retry_on_timeout,
    max_connections=settings.redis_max_connections,
    health_check_interval=30,
    auto_close_connection_pool=True,
)


def get_db() -> Generator[Session, None, None]:
    """
    SQLAlchemy 엔진을 사용하여 데이터베이스 세션을 생성하고 반환합니다.
    이 함수는 FastAPI의 Depends 의존성 주입 시스템에서 사용되며, 데이터베이스 세션을 제공하는 데 사용됩니다.
    """
    with Session(engine) as session:
        yield session


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Redis 클라이언트를 반환하는 비동기 의존성 주입 함수입니다.
    이 함수는 FastAPI의 Depends 의존성 주입 시스템에서 사용되며, Redis 클라이언트를 제공하는 데 사용됩니다.
    """
    try:
        await redis_client.ping()
        yield redis_client
    finally:
        await redis_client.close()
