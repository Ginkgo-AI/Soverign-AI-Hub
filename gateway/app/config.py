from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "info"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "sovereign_ai"
    postgres_user: str = "sovereign"
    postgres_password: str = "changeme_in_production"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # LLM backends
    vllm_host: str = "vllm"
    vllm_port: int = 8000
    llama_cpp_host: str = "llama-cpp"
    llama_cpp_port: int = 8080

    # Gateway
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8888
    gateway_secret_key: str = "dev-secret-change-in-production"
    gateway_cors_origins: str = "http://localhost:3000"

    # Modes
    airgap_mode: bool = False

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def vllm_base_url(self) -> str:
        return f"http://{self.vllm_host}:{self.vllm_port}/v1"

    @property
    def llama_cpp_base_url(self) -> str:
        return f"http://{self.llama_cpp_host}:{self.llama_cpp_port}/v1"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.gateway_cors_origins.split(",")]

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
