from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    s3_bucket_name: str
    max_file_size: int = Field(default=52428800)  # 50MB default

    model_config = SettingsConfigDict(env_file='.env', case_sensitive=False)

settings = Settings() 