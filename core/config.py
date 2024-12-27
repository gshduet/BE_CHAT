from functools import lru_cache

from boto3 import client
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
    aws_elasticache_port: str = Field(..., env="AWS_ELASTICACHE_PORT")

    aws_s3_bucket_name: str = Field(..., env="AWS_S3_BUCKET_NAME")

    def get_db_url(self) -> str:
        return f"postgresql://{self.aws_rds_db_username}:{self.aws_rds_db_password}@{self.aws_rds_db_host}:{self.aws_rds_db_port}/{self.aws_rds_db_name}"

    def get_aws_s3_client(self) -> client:
        return client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region,
        )

    @property
    def db_url(self) -> str:
        return self.get_db_url()

    @property
    def aws_s3_client(self) -> client:
        return self.get_aws_s3_client()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
