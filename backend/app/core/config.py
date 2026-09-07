import os
from pathlib import Path
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the backend directory location reliably based on this file's path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_ENV_FILE = str(BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "MIRRAGE API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | production | testing

    # Security & Authentication
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info: ValidationInfo) -> str:
        env = info.data.get("ENVIRONMENT", "development")
        if env == "testing":
            return v
        
        insecure_terms = ["mirrage", "changeme", "secret", "test"]
        is_insecure = len(v) < 32 or any(term in v.lower() for term in insecure_terms)
        
        if env == "production" and is_insecure:
            raise ValueError(
                "SECRET_KEY in production must be at least 32 characters long "
                "and not contain common insecure words like 'mirrage', 'test', etc."
            )
        elif env == "development" and is_insecure:
            import warnings
            warnings.warn("SECRET_KEY is weak or uses default insecure patterns. Consider changing it.")
            
        return v

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://mirrage.vercel.app",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./mirrage.db"

    # Session & Slot Management
    MAX_CONCURRENT_SESSIONS: int = 3
    SESSION_TIMEOUT_MINUTES: int = 30
    SESSION_CLEANUP_INTERVAL_SECONDS: int = 60
    INITIALIZATION_SIMULATION_SECONDS: int = 5

    # Kubernetes / k3s Engine
    K8S_MODE: str = "mock"
    K8S_NAMESPACE: str = "mirrage-sessions"
    K8S_IN_CLUSTER: bool = False
    K8S_KUBECONFIG_PATH: str = os.path.expanduser("~/.kube/config")
    MIRAGE_CONTAINER_IMAGE: str = "mirrage/mirage-honeypot:latest"
    CTF_CONTAINER_IMAGE: str = "mirrage/ctf-core:latest"
    DEFAULT_POD_SUBNET_PREFIX: str = "10.42.0."

    # OpenVPN Engine
    VPN_MODE: str = "mock"
    OPENVPN_SERVER_HOST: str = "vpn.mirrage.internal"
    OPENVPN_SERVER_PORT: int = 1194
    OPENVPN_PROTO: str = "udp"
    OPENVPN_CA_PATH: str = "/etc/openvpn/ca.crt"
    OPENVPN_STATUS_LOG_PATH: str = "/var/log/openvpn/openvpn-status.log"
    DEFAULT_VPN_SUBNET_PREFIX: str = "10.8.0."
    
    ALLOW_MOCK_IN_PRODUCTION: bool = False

    def validate_production_config(self):
        if self.ENVIRONMENT == "production":
            if self.K8S_MODE != "production" and not self.ALLOW_MOCK_IN_PRODUCTION:
                raise ValueError("K8S_MODE must be 'production' in production environment unless ALLOW_MOCK_IN_PRODUCTION is true")
            if self.VPN_MODE != "production" and not self.ALLOW_MOCK_IN_PRODUCTION:
                raise ValueError("VPN_MODE must be 'production' in production environment unless ALLOW_MOCK_IN_PRODUCTION is true")
            
            insecure_terms = ["mirrage", "changeme", "secret", "test"]
            is_insecure = len(self.SECRET_KEY) < 32 or any(term in self.SECRET_KEY.lower() for term in insecure_terms)
            if is_insecure:
                raise ValueError("SECRET_KEY in production is insecure")

settings = Settings()
