import os
import ipaddress
import math
from email_validator import validate_email, EmailNotValidError
from pathlib import Path
from typing import List, Union
from pydantic import AnyHttpUrl, Field, field_validator, ValidationInfo
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
    OTP_HMAC_SECRET: str = ""
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

    @field_validator("OTP_HMAC_SECRET")
    @classmethod
    def validate_otp_hmac_secret(cls, v: str, info: ValidationInfo) -> str:
        env = info.data.get("ENVIRONMENT", "development")
        if env == "testing":
            return v or "test-otp-hmac-secret-not-for-production-min-32-chars"
        
        if env == "production":
            if not v:
                raise ValueError("OTP_HMAC_SECRET is required in production")
            insecure_terms = ["mirrage", "changeme", "secret", "test", "default"]
            is_insecure = len(v) < 32 or any(term in v.lower() for term in insecure_terms)
            if is_insecure:
                raise ValueError(
                    "OTP_HMAC_SECRET in production must be at least 32 characters long "
                    "and not contain common insecure words like 'mirrage', 'test', etc."
                )
        elif env == "development":
            if not v:
                # Provide a sensible dev fallback if not set
                return "dev-otp-hmac-secret-must-be-at-least-32-characters-long"
            if len(v) < 32:
                import warnings
                warnings.warn("OTP_HMAC_SECRET is weak. Consider using a 32+ character random secret.")
        return v

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://mirrage.vercel.app",
        "https://themirrage.me",
        "https://www.themirrage.me",
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

    # Same three shared flags are used by the API and all player targets.
    # Relative paths resolve from backend/. No plaintext flag values in env vars.
    CTF_FLAGS_FILE: str = ""
    FLAG_SUBMISSIONS_PER_WINDOW: int = 10
    FLAG_SUBMISSION_WINDOW_SECONDS: int = 60

    @field_validator("FLAG_SUBMISSIONS_PER_WINDOW", "FLAG_SUBMISSION_WINDOW_SECONDS")
    @classmethod
    def validate_flag_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Flag submission limits must be positive")
        return value

    # OTP Configuration
    OTP_EXPIRY_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_REQUESTS_PER_WINDOW: int = 5
    OTP_RATE_LIMIT_WINDOW_MINUTES: int = 30
    OTP_DEV_MODE: bool = False
    OTP_IP_REQUEST_LIMIT: int = 10
    OTP_IP_WINDOW_SECONDS: int = 600
    OTP_EMAIL_HOURLY_LIMIT: int = 100
    OTP_EMAIL_DAILY_LIMIT: int = 500
    OTP_IP_BUCKET_RETENTION_SECONDS: int = 86400
    # Immediate Nginx peers only. No header is trusted by default.
    OTP_TRUSTED_PROXY_CIDRS: List[str] = []

    @field_validator("OTP_IP_REQUEST_LIMIT", "OTP_IP_WINDOW_SECONDS", "OTP_EMAIL_HOURLY_LIMIT",
                     "OTP_EMAIL_DAILY_LIMIT", "OTP_IP_BUCKET_RETENTION_SECONDS")
    @classmethod
    def validate_otp_abuse_limits(cls, value):
        if value < 1:
            raise ValueError("OTP abuse limits must be positive")
        return value

    @field_validator("OTP_TRUSTED_PROXY_CIDRS")
    @classmethod
    def validate_otp_proxy_networks(cls, values):
        networks = [ipaddress.ip_network(value) for value in values]
        if any(network.prefixlen == 0 for network in networks):
            raise ValueError("Wildcard OTP proxy trust is forbidden")
        return [str(network) for network in networks]

    # Email Configuration
    EMAIL_PROVIDER: str = ""
    EMAIL_API_KEY: str = ""
    EMAIL_FROM: str = ""
    EMAIL_FROM_NAME: str = "MIRRAGE"
    EMAIL_REPLY_TO: str = ""
    # Legacy field retained for parsing; configure EMAIL_FROM explicitly for dispatch.
    EMAIL_FROM_ADDRESS: str = "noreply@mirrage.io"
    EMAIL_TIMEOUT_SECONDS: float = 10.0
    EMAIL_HEALTH_RETENTION_DAYS: int = 7

    @field_validator("EMAIL_TIMEOUT_SECONDS")
    @classmethod
    def validate_email_timeout(cls, value):
        if not math.isfinite(value) or not 0 < value <= 60:
            raise ValueError("EMAIL_TIMEOUT_SECONDS must be positive and at most 60")
        return value

    @field_validator("EMAIL_HEALTH_RETENTION_DAYS")
    @classmethod
    def validate_email_retention(cls, value):
        if value < 1:
            raise ValueError("EMAIL_HEALTH_RETENTION_DAYS must be positive")
        return value

    def email_configuration_error(self):
        if self.EMAIL_PROVIDER.strip().lower() not in {"resend", "sendgrid"}:
            return "EMAIL_PROVIDER_UNSUPPORTED"
        if (not self.EMAIL_API_KEY or not self.EMAIL_API_KEY.isascii()
                or any(char.isspace() or not char.isprintable() for char in self.EMAIL_API_KEY)):
            return "EMAIL_API_KEY_INVALID"
        for value, code, required in ((self.EMAIL_FROM, "EMAIL_FROM_INVALID", True),
                                       (self.EMAIL_REPLY_TO, "EMAIL_REPLY_TO_INVALID", False)):
            if not value and not required:
                continue
            try:
                if not value or any(ord(char) < 32 for char in value):
                    return code
                validate_email(value, check_deliverability=False, allow_smtputf8=False)
            except EmailNotValidError:
                return code
        if len(self.EMAIL_FROM_NAME) > 128 or any(ord(char) < 32 for char in self.EMAIL_FROM_NAME):
            return "EMAIL_FROM_NAME_INVALID"
        return None

    # Session & Slot Management
    MAX_CONCURRENT_SESSIONS: int = 5
    SESSION_TIMEOUT_MINUTES: int = 90
    SESSION_MAX_DURATION_MINUTES: int = 300  # 5 hours max total lifetime
    SESSION_CLEANUP_INTERVAL_SECONDS: int = 60
    INITIALIZATION_SIMULATION_SECONDS: int = 5

    # Kubernetes / k3s Engine
    K8S_MODE: str = "mock"
    K8S_NAMESPACE: str = "mirrage-sessions"
    K8S_IN_CLUSTER: bool = False
    K8S_KUBECONFIG_PATH: str = os.getenv("K8S_KUBECONFIG_PATH", os.path.expanduser("~/.kube/config"))
    MIRAGE_CONTAINER_IMAGE: str = "docker.io/library/mirrage-mirrage:latest"
    CTF_CONTAINER_IMAGE: str = "docker.io/library/mirrage-ctf:latest"
    DEFAULT_POD_SUBNET_PREFIX: str = "10.42.0."

    # OpenVPN Engine
    VPN_MODE: str = "mock"
    VPN_DOWNLOAD_LIMIT_PER_SESSION: int = Field(default=3, ge=1)
    OPENVPN_SERVER_HOST: str = "vpn.mirrage.internal"
    OPENVPN_SERVER_PORT: int = 1194
    OPENVPN_PROTO: str = "udp"
    OPENVPN_CA_PATH: str = "/etc/openvpn/ca.crt"
    OPENVPN_STATUS_LOG_PATH: str = "/var/log/openvpn/status.log"
    DEFAULT_VPN_SUBNET_PREFIX: str = "10.8.0."
    VPN_CLIENT_CIDR: str = "10.8.0.0/24"
    VPN_CLIENT_IP_START: str = "10.8.0.10"
    VPN_CLIENT_IP_END: str = "10.8.0.250"
    OPENVPN_CCD_DIR: str = "/var/lib/mirrage/openvpn/ccd"
    OPENVPN_TUN_INTERFACE: str = "tun0"
    VPN_CONTROL_HELPER: str = "/usr/local/sbin/mirrage-vpn-control"
    VPN_PKI_TIMEOUT_SECONDS: int = 45
    VPN_REVOCATION_RETRY_SECONDS: int = 30
    VPN_CRL_CHECK_INTERVAL_SECONDS: int = 3600
    VPN_CRL_REFRESH_MARGIN_SECONDS: int = 7 * 24 * 3600

    @field_validator("VPN_PKI_TIMEOUT_SECONDS", "VPN_REVOCATION_RETRY_SECONDS",
                     "VPN_CRL_CHECK_INTERVAL_SECONDS", "VPN_CRL_REFRESH_MARGIN_SECONDS")
    @classmethod
    def validate_vpn_operation_timing(cls, value: int) -> int:
        if value < 1:
            raise ValueError("VPN operation timing must be positive")
        return value
    SESSION_POD_CIDR: str = "10.42.0.0/16"
    SESSION_POD_INTERFACE: str = "cni0"
    K8S_SESSION_NODE_NAME: str = ""
    SESSION_CALLBACK_PORTS: List[int] = [4444]
    SESSION_GATEWAY_HELPER: str = "/usr/local/sbin/mirrage-session-access"

    @field_validator("SESSION_CALLBACK_PORTS")
    @classmethod
    def validate_callback_ports(cls, value: List[int]) -> List[int]:
        if any(port < 1 or port > 65535 for port in value):
            raise ValueError("Callback ports must be between 1 and 65535")
        return sorted(set(value))

    # Easy-RSA / Production VPN Provisioning
    EASYRSA_DIR: str = os.path.expanduser("~/openvpn-ca")
    EASYRSA_CA_CERT: str = os.path.expanduser("~/openvpn-ca/pki/ca.crt")
    EASYRSA_TLS_KEY: str = os.path.expanduser("~/openvpn-ca/ta.key")
    VPN_CA_PASSPHRASE_FILE: str = "/etc/mirrage/vpn-ca-passphrase"
    VPN_CLIENT_NAME_PREFIX: str = "mirrage"
    
    ALLOW_MOCK_IN_PRODUCTION: bool = False

    def validate_production_config(self):
        if self.K8S_MODE == "production" and self.VPN_MODE != "production":
            raise ValueError("Real player sessions require production VPN reservations")
        if self.ENVIRONMENT == "production":
            if self.K8S_MODE != "production" and not self.ALLOW_MOCK_IN_PRODUCTION:
                raise ValueError("K8S_MODE must be 'production' in production environment unless ALLOW_MOCK_IN_PRODUCTION is true")
            if self.VPN_MODE != "production" and not self.ALLOW_MOCK_IN_PRODUCTION:
                raise ValueError("VPN_MODE must be 'production' in production environment unless ALLOW_MOCK_IN_PRODUCTION is true")
            if self.OTP_DEV_MODE:
                raise ValueError("OTP_DEV_MODE must be false in production to prevent OTP leakage to logs")
            
            insecure_terms = ["mirrage", "changeme", "secret", "test", "default"]
            is_insecure = len(self.SECRET_KEY) < 32 or any(term in self.SECRET_KEY.lower() for term in insecure_terms)
            if is_insecure:
                raise ValueError("SECRET_KEY in production is insecure")
            
            if not self.OTP_HMAC_SECRET or len(self.OTP_HMAC_SECRET) < 32 or any(term in self.OTP_HMAC_SECRET.lower() for term in insecure_terms):
                raise ValueError("OTP_HMAC_SECRET in production must be at least 32 characters long and secure")
            if error := self.email_configuration_error():
                raise ValueError(f"Production email configuration is invalid ({error})")
        if self.K8S_MODE == "production" and not self.K8S_SESSION_NODE_NAME:
            raise ValueError("K8S_SESSION_NODE_NAME must identify the node running the VPN/gateway guard")

settings = Settings()
