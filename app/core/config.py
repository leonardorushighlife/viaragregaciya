from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "MALVIK-LABEL"
    DATABASE_URL: str = "sqlite:///./malvik_label.db"

    # Email Settings
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@malvik.ru"

    # Chestny Znak Settings
    CHESTNY_ZNAK_STUB: bool = True
    CHESTNY_ZNAK_API_KEY: str = "mock_key_12345"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
