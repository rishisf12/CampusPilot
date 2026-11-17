from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./mail.db"
    SECRET_KEY: str = "dev-secret-change-me"

    class Config:
        env_file = ".env"


settings = Settings()
