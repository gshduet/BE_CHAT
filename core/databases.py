from typing import Generator

from boto3 import client
from fastapi import Depends
from redis import Redis
from sqlmodel import Session, create_engine

from core.config import settings


engine = create_engine(
    settings.db_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)


def get_db() -> Generator[Session, None, None]:
    """
    SQLAlchemy 엔진을 사용하여 데이터베이스 세션을 생성하고 반환합니다.
    이 함수는 FastAPI의 Depends 의존성 주입 시스템에서 사용되며, 데이터베이스 세션을 제공하는 데 사용됩니다.
    """
    with Session(engine) as session:
        yield session


def get_redis() -> Redis:
    """
    AWS ElastiCache for Redis에 연결하는 클라이언트를 생성합니다.
    SSL/TLS 연결, 연결 타임아웃, 재시도 설정 등 AWS ElastiCache에 필요한 기본적인 설정들을 포함합니다.
    클러스터 모드가 활성화된 경우에는 추가 설정이 필요할 수 있습니다.
    이 함수는 FastAPI의 Depends 의존성 주입 시스템에서 사용되며, redis 클라이언트를 제공하는 데 사용됩니다.
    """
    return Redis(
        host=settings.aws_elasticache_endpoint,
        port=settings.aws_elasticache_port,
        # ssl=True,
        # ssl_cert_reqs=None,
        socket_timeout=5.0,
        socket_connect_timeout=2.0,
        retry_on_timeout=True,
        max_connections=10,
    )


def _s3_client() -> client:
    """
    AWS S3 클라이언트를 생성합니다.
    이 함수는 FastAPI의 Depends 의존성 주입 시스템에서 사용되며, S3 클라이언트를 제공하는 데 사용됩니다.
    """
    return client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


class S3Manager:
    """
    AWS S3 버킷에 대한 파일 업로드 및 다운로드를 관리하는 클래스입니다.
    S3 클라이언트를 사용하여 파일 업로드, 다운로드, 삭제 등의 작업을 수행합니다.
    모든 메서드는 예외 처리를 포함하여 안전한 S3 작업을 보장합니다.
    """

    def __init__(self, s3_client: client = Depends(_s3_client)):
        self.client = s3_client

    async def upload_file(
        self,
        file_key: str,
        file_data: bytes,
        bucket: str = settings.aws_s3_bucket_name,
    ) -> bool:
        """
        바이트 데이터를 S3 버킷에 업로드합니다.

        Args:
            bucket: 대상 S3 버킷 이름
            file_key: 저장될 파일의 키(경로)
            file_data: 업로드할 파일의 바이트 데이터

        Returns:
            업로드 성공 여부를 나타내는 bool 값
        """
        try:
            self.client.upload_fileobj(Bucket=bucket, Key=file_key, Body=file_data)
            return True

        except Exception as e:
            print(f"파일 업로드 중 오류 발생: {str(e)}")
            return False

    async def download_file(self, bucket: str, file_key: str) -> bytes | None:
        """
        S3 버킷에서 파일을 다운로드합니다.

        Args:
            bucket: 대상 S3 버킷 이름
            file_key: 다운로드할 파일의 키(경로)

        Returns:
            다운로드한 파일의 바이트 데이터 또는 실패 시 None
        """
        try:
            response = self.client.get_object(Bucket=bucket, Key=file_key)
            return response["Body"].read()

        except Exception as e:
            print(f"파일 다운로드 중 오류 발생: {str(e)}")
            return None

    async def delete_file(self, bucket: str, file_key: str) -> bool:
        """
        S3 버킷에서 파일을 삭제합니다.

        Args:
            bucket: 대상 S3 버킷 이름
            file_key: 삭제할 파일의 키(경로)

        Returns:
            삭제 성공 여부를 나타내는 bool 값
        """
        try:
            self.client.delete_object(Bucket=bucket, Key=file_key)
            return True

        except Exception as e:
            print(f"파일 삭제 중 오류 발생: {str(e)}")
            return False
