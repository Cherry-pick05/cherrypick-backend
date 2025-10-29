from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "cherrypick"
    port: int = 8000

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "cp_user"
    mysql_password: str = "cp_pass"
    mysql_db: str = "cherrypick"

    s3_bucket: str = "cherrypick-item-crops"
    aws_region: str = "ap-northeast-2"
    aws_endpoint_url: str | None = "http://localhost:4566"  # LocalStack edge
    guest_hmac_secret: str = "change_me"

    # Redis / CORS / Client
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ]
    client_id_header: str = "X-Client-Id"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


settings = Settings()


