import logging
import os

from dotenv import load_dotenv

load_dotenv()


class AppConfig:
    AGENT_URL: str = os.getenv("GATEWAY__AGENT_URL", "http://localhost:8001")
    INTERNAL_API_KEY: str = os.getenv("GATEWAY__INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("GATEWAY__LOG_LEVEL", "DEBUG")
    REQUEST_TIMEOUT: float = float(os.getenv("GATEWAY__REQUEST_TIMEOUT", "30.0"))
    AGENT_STREAM_TIMEOUT: float = float(os.getenv("GATEWAY__AGENT_STREAM_TIMEOUT", "60.0"))
    VERSION: str = os.getenv("GATEWAY__VERSION", "0.1.0")
    
    # Auth Service settings
    AUTH_SERVICE_URL: str = os.getenv("GATEWAY__AUTH_SERVICE_URL", "http://auth-service:8003")
    USE_JWT_AUTH: bool = os.getenv("GATEWAY__USE_JWT_AUTH", "false").lower() == "true"
    
    @property
    def JWKS_URL(self) -> str:
        return f"{self.AUTH_SERVICE_URL}/.well-known/jwks.json"


logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("gateway")
