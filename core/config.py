from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field(..., env="ALGORITHM")
    access_token_expire_hours: int = Field(..., env="ACCESS_TOKEN_EXPIRE_HOURS")

    db_pool_size: int = Field(..., env="DB_POOL_SIZE")
    db_max_overflow: int = Field(..., env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(..., env="DB_POOL_TIMEOUT")

    aws_region: str = Field(..., env="AWS_REGION")
    aws_access_key_id: str = Field(..., env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., env="AWS_SECRET_ACCESS_KEY")

    aws_rds_db_name: str = Field(..., env="AWS_RDS_DB_NAME")
    aws_rds_db_username: str = Field(..., env="AWS_RDS_DB_USERNAME")
    aws_rds_db_password: str = Field(..., env="AWS_RDS_DB_PASSWORD")
    aws_rds_db_host: str = Field(..., env="AWS_RDS_DB_HOST")
    aws_rds_db_port: str = Field(..., env="AWS_RDS_DB_PORT")

    aws_elasticache_endpoint: str = Field(..., env="AWS_ELASTICACHE_ENDPOINT")
    aws_elasticache_port: int = Field(..., env="AWS_ELASTICACHE_PORT")
    redis_socket_timeout: float = Field(5.0, env="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: float = Field(2.0, env="REDIS_SOCKET_CONNECT_TIMEOUT")
    redis_retry_on_timeout: bool = Field(True, env="REDIS_RETRY_ON_TIMEOUT")
    redis_max_connections: int = Field(10, env="REDIS_MAX_CONNECTIONS")

    rooms_key_template: str = Field(..., env="ROOMS_KEY_TEMPLATE")
    client_key_template: str = Field(..., env="CLIENT_KEY_TEMPLATE")
    sid_key_template: str = Field(..., env="SID_KEY_TEMPLATE")
    disconnected_client_key_template: str = Field(
        ..., env="DISCONNECTED_CLIENT_KEY_TEMPLATE"
    )
    meeting_room_key_template: str = Field(..., env="MEETING_ROOM_KEY_TEMPLATE")
    client_sid_key_template: str = Field(..., env="CLIENT_SID_KEY_TEMPLATE")

    def get_db_url(self) -> str:
        return f"postgresql://{self.aws_rds_db_username}:{self.aws_rds_db_password}@{self.aws_rds_db_host}:{self.aws_rds_db_port}/{self.aws_rds_db_name}"

    @property
    def db_url(self) -> str:
        return self.get_db_url()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
