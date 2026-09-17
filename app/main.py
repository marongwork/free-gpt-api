import logging
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from app.config import settings
from app.prism_client import PrismClient
from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelCard,
    ModelList,
)
from app.sse_adapter import non_stream_chat_completion, stream_chat_completion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("prism_proxy")

app = FastAPI(
    title="OpenAI Prism Reverse Proxy",
    description="High-reasoning (Astra xhigh) API proxy bridging OpenAI Prism to standard OpenAI format",
    version="1.0.0"
)

# 允许跨域请求 (适配 Web 客户端如 NextChat / OpenWebUI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_prism_credentials(
    authorization: Optional[str] = Header(None),
    cookie: Optional[str] = Header(None)
) -> PrismClient:
    """解析凭据策略：优先使用客户端传入的 Token，其次使用服务端内置的默认配置"""
    token = ""
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            token = authorization

    # 如果配置了代理保护 Key，且客户端传入的是保护 Key，则自动切换为服务端统一预设的 Prism Token
    if settings.PROXY_API_KEY:
        if token == settings.PROXY_API_KEY:
            token = settings.DEFAULT_PRISM_TOKEN
        elif not token.startswith("ey"):
            raise HTTPException(status_code=401, detail="Invalid Proxy API Key")

    final_token = token or settings.DEFAULT_PRISM_TOKEN
    final_cookie = cookie or settings.DEFAULT_PRISM_COOKIE

    if not final_token and not final_cookie:
        logger.warning("No Prism Token or Cookie provided in request or environment.")

    return PrismClient(token=final_token, cookie=final_cookie)


@app.get("/")
@app.get("/health")
@app.get("/v1/health")
async def health_check():
    return {
        "status": "online",
        "service": "OpenAI Prism Reverse Proxy",
        "target": settings.PRISM_BASE_URL,
        "default_model": settings.DEFAULT_MODEL
    }


@app.get("/v1/models", response_model=ModelList)
@app.get("/models", response_model=ModelList)
async def list_models():
    cards = [ModelCard(id=m) for m in settings.SUPPORTED_MODELS]
    return ModelList(data=cards)


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    prism_client: PrismClient = Depends(get_prism_credentials)
):
    # 将模型名归一化
    model = req.model or settings.DEFAULT_MODEL
    messages_dicts = [m.model_dump() for m in req.messages]

    logger.info(f"Incoming chat completion request: model={model}, reasoning_effort={req.reasoning_effort}, messages_count={len(messages_dicts)}, stream={req.stream}")

    if req.stream:
        # 流式返回 (SSE)
        response_generator = stream_chat_completion(
            prism_client=prism_client,
            messages=messages_dicts,
            model=model,
            tools=req.tools,
            reasoning_effort=req.reasoning_effort
        )
        return StreamingResponse(
            response_generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "X-Accel-Buffering": "no"  # 关闭 Nginx 缓冲，确保实时吐字
            }
        )
    else:
        # 非流式聚合返回
        res = await non_stream_chat_completion(
            prism_client=prism_client,
            messages=messages_dicts,
            model=model,
            tools=req.tools,
            reasoning_effort=req.reasoning_effort
        )
        return res
