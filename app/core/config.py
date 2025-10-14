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
    guest_hmac_secret: str = "change_me"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


settings = Settings()


