from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://sports:sports123@db:5432/sportsdb"
    REDIS_URL: str = "redis://redis:6379/0"
    DAY1_SALT: str = "demo-salt"
    JWT_SECRET: str = "nascon26-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET: str = "receipts"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
