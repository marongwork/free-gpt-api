import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # 服务端配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Prism 官方接口配置
    PRISM_BASE_URL: str = os.getenv("PRISM_BASE_URL", "https://prism.openai.com").rstrip("/")
    
    # 默认 Prism 凭据 (可在客户端请求时由 Authorization Header 覆盖，也可作为服务端统一凭据)
    DEFAULT_PRISM_TOKEN: str = os.getenv("PRISM_TOKEN", "")
    DEFAULT_PRISM_COOKIE: str = os.getenv("PRISM_COOKIE", "")
    
    # 预设常驻 Project UUID (若不填则会自动调用 POST /api/projects 创建并缓存)
    DEFAULT_PROJECT_ID: str = os.getenv("DEFAULT_PROJECT_ID", "")
    
    # 反代服务自身的鉴权 Key（防盗刷；留空则表示不对上游客户端做鉴权校验）
    PROXY_API_KEY: str = os.getenv("PROXY_API_KEY", "")
    
    # 轮询与超时配置
    POLL_INTERVAL_MS: int = int(os.getenv("POLL_INTERVAL_MS", "500"))
    POLL_MAX_RETRIES: int = int(os.getenv("POLL_MAX_RETRIES", "600"))  # 600 * 500ms = 300s
    HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "300.0"))
    
    # 虚拟模型映射表
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "o1-astra-xhigh")
    SUPPORTED_MODELS: List[str] = [
        "o1-astra-xhigh",
        "o1-high",
        "o3-high",
        "o1-preview",
        "gpt-5.2-prism",
        "gpt-4o",
        "astra-xhigh"
    ]

settings = Settings()
