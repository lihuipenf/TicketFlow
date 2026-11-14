from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    database_url: SecretStr = SecretStr('mysql+pymysql://ticketflow@127.0.0.1:3307/ticketflow')
    jwt_secret: SecretStr = SecretStr('')
    admin_password: SecretStr = SecretStr('')
    supervisor_password: SecretStr = SecretStr('')
    agent_password: SecretStr = SecretStr('')
    knowledge_password: SecretStr = SecretStr('')
    llm_api_key: SecretStr = SecretStr('')
    llm_provider: str = 'qwen'
    llm_base_url: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    llm_model: str = 'qwen3.5-plus'
    llm_api_mode: str = 'chat'
    embedding_model: str = 'Qwen/Qwen3-Embedding-0.6B'
    embedding_device: str = 'cpu'
    hf_home: str = 'D:/CodexData/caches/huggingface'
    data_dir: Path = ROOT / 'data'
    cors_origins: str = 'http://127.0.0.1:5173,http://localhost:5173'
    upload_max_request_bytes: int = Field(default=10 * 1024 * 1024 + 64 * 1024, ge=1024, le=16 * 1024 * 1024)
    upload_timeout_seconds: float = Field(default=30, ge=0.01, le=300)
    upload_max_concurrent: int = Field(default=2, ge=1, le=8)

    @property
    def storage(self) -> Path:
        return self.data_dir if self.data_dir.is_absolute() else ROOT / self.data_dir


@lru_cache
def settings():
    return Settings()
