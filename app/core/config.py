from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[import-not-found]


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "cherrypick"
    port: int = 8000

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "cp_user"
    mysql_password: str = "cp_pass"  # Must match docker-compose.yml MYSQL_PASSWORD
    mysql_db: str = "cherrypick"

    s3_bucket: str = "cherrypick-item-crops"
    aws_region: str = "ap-northeast-2"
    aws_endpoint_url: str | None = "http://localhost:4566"  # LocalStack edge
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    guest_hmac_secret: str = "change_me"
    device_uuid_header: str = "X-Device-UUID"
    device_token_header: str = "X-Device-Token"
    device_token_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days
    device_token_version: int = 1
    device_recovery_code_ttl_hours: int = 24 * 14
    device_recovery_code_length: int = 8
    device_recovery_code_charset: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    # Redis / CORS / Client
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] | str = "*"  # 개발 환경 기본값: 모든 origin 허용

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str] | str:
        if isinstance(v, str):
            if v == "*":
                return "*"
            # 쉼표로 구분된 문자열을 리스트로 변환
            if "," in v:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
            # 단일 origin
            return [v.strip()] if v.strip() else "*"
        if isinstance(v, list):
            return v
        return "*"

    client_id_header: str = "X-Client-Id"
    gemini_model: str = "models/gemini-2.5-flash-lite"
    gemini_api_key: str | None = None
    llm_classifier_temperature: float = 0.0
    llm_classifier_max_tokens: int = 256
    llm_classifier_timeout_sec: float = 8.0
    llm_classifier_cache_ttl_seconds: int = 60 * 60 * 24 * 7
    llm_classifier_confidence_threshold: float = 0.7
    llm_classifier_enabled: bool = True
    llm_classifier_l1_cache_size: int = 256

    llm_tips_enabled: bool = True
    llm_tips_model: str | None = None
    llm_tips_temperature: float = 0.2
    llm_tips_max_tokens: int = 256
    llm_tips_timeout_sec: float = 6.0

    # Travel recommendation integrations
    weather_api_key: str | None = None
    weather_api_base_url: str = "https://api.openweathermap.org/data/2.5"
    weather_units: str = "metric"
    weather_lang: str = "kr"
    weather_timeout_sec: float = 5.0

    # Frankfurter API (ECB reference rates)
    frankfurter_api_base_url: str = "https://api.frankfurter.dev"
    frankfurter_timeout_sec: float = 5.0
    fx_cache_ttl_latest_sec: int = 60  # 1 minute for latest rates
    fx_cache_ttl_historical_sec: int = 60 * 60 * 24  # 24 hours for historical rates

    molit_service_key: str | None = None
    molit_airport_dataset_id: str = "uddi:12f91d16-ea50-48d1-bdc3-df8410f22542"
    molit_airport_base_url: str = "https://api.odcloud.kr/api/3051587/v1"

    # AirLabs flight lookup
    airlabs_api_key: str | None = None
    airlabs_api_base_url: str = "https://airlabs.co/api/v9"
    airlabs_timeout_sec: float = 6.0

    # Meteostat climate data
    meteostat_api_key: str | None = None
    meteostat_base_url: str = "https://meteostat.p.rapidapi.com"
    meteostat_timeout_sec: float = 6.0

    safe_mode_default: bool = True
    supported_locales: list[str] = ["ko-KR", "en-US"]
    units_defaults: dict[str, str] = {"weight": "kg", "length": "cm"}
    ui_flags_defaults: dict[str, Any] = {"show_reco_tab": True, "max_payload_kb": 256}
    feature_flags_defaults: dict[str, bool] = {"safety_mode": True, "tips_enabled": True}
    ab_test_buckets: list[str] = ["control", "variant"]
    rules_manifest_version: str = "2024-11-01"
    taxonomy_manifest_version: str = "2024-11-01"
    
    # 서비스 중인 국가 목록 (ISO 3166-1 alpha-2 코드)
    # active_only=True일 때 이 목록에 있는 국가만 반환됩니다
    supported_countries: list[str] = ["KR", "US"]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def sqlalchemy_url(self) -> str:
        # Force TCP/IP connection by adding unix_socket= parameter
        # This prevents MySQL from using Unix socket for localhost connections
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4&unix_socket="
        )


settings = Settings()


