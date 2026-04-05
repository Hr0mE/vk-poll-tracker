from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    vk_token: str = ""
    vk_api_version: str = "5.131"
    peer_id: int = 0
    rate_limit_per_sec: int = 3
    max_concurrent_requests: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
