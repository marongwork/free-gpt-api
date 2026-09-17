import asyncio
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import httpx

from app.config import settings

logger = logging.getLogger("prism_client")

# Prism internal model mapping
MODEL_MAPPING = {
    "o1-astra-xhigh": "gpt-5.6-terra",
    "01-astra-xhigh": "gpt-5.6-terra",
    "astra-xhigh": "gpt-5.6-terra",
    "o1-high": "gpt-5.6-terra",
    "01-high": "gpt-5.6-terra",
    "o3-high": "gpt-5.6-terra",
    "03-high": "gpt-5.6-terra",
    "o1": "gpt-5.6-terra",
    "01": "gpt-5.6-terra",
    "o1-preview": "gpt-5.6-terra",
    "01-preview": "gpt-5.6-terra",
    "gpt-6-astra": "gpt-5.6-terra",
    "gpt-5.6-terra": "gpt-5.6-terra",
    "gpt-5.6-sol": "gpt-5.6-sol",
    "gpt-4o": "gpt-4o",
    "gpt-5.2-prism": "gpt-5.6-terra",
}

def map_model(model_name: Optional[str]) -> str:
    key = (model_name or "").strip().lower()
    if key in MODEL_MAPPING:
        return MODEL_MAPPING[key]
    if key.startswith("01"):
        key = "o1" + key[2:]
        if key in MODEL_MAPPING:
            return MODEL_MAPPING[key]
    if key.startswith("03"):
        key = "o3" + key[2:]
        if key in MODEL_MAPPING:
            return MODEL_MAPPING[key]
    return "gpt-5.6-terra"

_GLOBAL_SANDBOX_CACHE: Dict[str, Any] = {}
_SANDBOX_LOCK = asyncio.Lock()


class PrismClient:
    def __init__(self, token: Optional[str] = None, cookie: Optional[str] = None):
        self.token = token or settings.DEFAULT_PRISM_TOKEN
        self.cookie = cookie or settings.DEFAULT_PRISM_COOKIE
        self.base_url = settings.PRISM_BASE_URL
        self._cached_project_id: Optional[str] = settings.DEFAULT_PROJECT_ID or None
        self._cached_user_id: Optional[str] = None

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
            "Content-Type": "application/json",
            "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        if self.token:
            clean_token = self.token.strip()
            if not clean_token.lower().startswith("bearer "):
                clean_token = f"Bearer {clean_token}"
            headers["Authorization"] = clean_token
        if self.cookie:
            headers["Cookie"] = self.cookie.strip()
        return headers

    async def get_or_create_project(self, client: httpx.AsyncClient) -> str:
        """获取现有项目或新建一个项目容器"""
        if self._cached_project_id:
            return self._cached_project_id

        # 查询已有项目
        try:
            resp = await client.get(f"{self.base_url}/api/projects", headers=self._get_headers())
            if resp.status_code == 200:
                projects = resp.json().get("projects", [])
                for p in projects:
                    if not p.get("deleted") and p.get("uuid"):
                        self._cached_project_id = str(p["uuid"])
                        if p.get("owner"):
                            self._cached_user_id = str(p["owner"])
                        logger.info(f"Using existing Prism project: {self._cached_project_id}")
                        return self._cached_project_id
        except Exception as e:
            logger.warning(f"List projects failed: {e}")

        # 新建项目
        url = f"{self.base_url}/api/projects"
        payload = {
            "title": "Document Workspace",
            "template": "blank"
        }
        try:
            resp = await client.post(url, json=payload, headers=self._get_headers())
            if resp.status_code in (200, 201):
                data = resp.json()
                if data.get("owner"):
                    self._cached_user_id = str(data["owner"])
                proj_id = data.get("id") or data.get("uuid") or data.get("project_id") or data.get("data", {}).get("id")
                if proj_id:
                    self._cached_project_id = str(proj_id)
                    logger.info(f"Successfully created Prism project: {self._cached_project_id}")
                    return self._cached_project_id
        except Exception as e:
            logger.error(f"Failed to create project: {e}")

        fallback_uuid = str(uuid.uuid4())
        self._cached_project_id = fallback_uuid
        return fallback_uuid

    async def ensure_sandbox_synced(self, client: httpx.AsyncClient, project_id: str) -> Tuple[str, str]:
        """
        完整的 Sandbox 握手与协同环境同步流程：
        1. POST /api/backend/1/new -> 获取 Sandbox 代理节点 URL 与 Token
        2. POST /api/projects/{projectId}/sandbox/resources-token -> 获取项目文件资源访问凭据
        3. POST {sb_url}resources-token -> 将资源凭据注入 Sandbox
        4. POST /api/y -> 获取 Yjs 协作文档服务鉴权配置
        5. POST {sb_url}token -> 将 Yjs 凭据同步给 Sandbox
        6. GET {sb_url}wait-for-sync?wait_ms=10000 -> 轮询等待沙箱完成工作区文件同步
        """
        async with _SANDBOX_LOCK:
            cached = _GLOBAL_SANDBOX_CACHE.get(project_id)
            if cached and (time.time() - cached["timestamp"] < 1800):
                return cached["url"], cached["token"]

            logger.info(f"Starting sandbox synchronization for project {project_id}...")
            # Step 1: POST /api/backend/1/new
            r1 = await client.post(f"{self.base_url}/api/backend/1/new", headers=self._get_headers())
            r1.raise_for_status()
            sb_data = r1.json()
            sb_url = sb_data["url"]
            sb_token = sb_data["token"]
            if not sb_url.endswith("/"):
                sb_url += "/"

            # Step 2: POST /api/projects/{project_id}/sandbox/resources-token
            r2 = await client.post(
                f"{self.base_url}/api/projects/{project_id}/sandbox/resources-token",
                headers=self._get_headers(),
                json={"sandbox_session_id": None, "sandbox_token": sb_token}
            )
            r2.raise_for_status()
            res_data = r2.json()
            acc_token = res_data.get("access_token")
            res_url = res_data.get("resources_base_url") or f"{self.base_url}/s/sandbox-resources"

            # Step 3: POST {sb_url}resources-token
            sb_headers = {
                **self._get_headers(),
                "X-Crixet-Sandbox-Token": sb_token,
                "Content-Type": "application/json"
            }
            r3 = await client.post(
                f"{sb_url}resources-token",
                headers=sb_headers,
                json={"token": acc_token, "resourceBaseUrl": res_url, "projectId": project_id}
            )
            r3.raise_for_status()

            # Step 4: POST /api/y
            r_y = await client.post(
                f"{self.base_url}/api/y",
                headers=self._get_headers(),
                json={
                    "docId": project_id,
                    "requestContext": {
                        "source": "initial-bootstrap",
                        "bootstrapAttempt": 0,
                        "previouslyConnected": False,
                        "sandboxUrl": sb_url,
                        "sandboxId": None,
                        "sandboxSessionId": None
                    }
                }
            )
            r_y.raise_for_status()
            y_data = r_y.json()

            # Step 5: POST {sb_url}token
            r_tok = await client.post(f"{sb_url}token", headers=sb_headers, json=y_data)
            r_tok.raise_for_status()

            # Step 6: GET {sb_url}wait-for-sync?wait_ms=10000
            for i in range(10):
                r_sync = await client.get(f"{sb_url}wait-for-sync?wait_ms=10000", headers=sb_headers)
                if r_sync.status_code == 200:
                    try:
                        sdata = r_sync.json()
                        if sdata.get("status") == "synced":
                            logger.info(f"Sandbox synced successfully in attempt {i}")
                            break
                    except Exception:
                        pass
                await asyncio.sleep(1)

            clean_url = sb_url.rstrip("/")
            _GLOBAL_SANDBOX_CACHE[project_id] = {
                "url": clean_url,
                "token": sb_token,
                "timestamp": time.time()
            }
            return clean_url, sb_token

    def _convert_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将 OpenAI messages 列表转换为 Prism 能够理解的完整多轮上下文输入。
        由于 Prism 底层作为单轮任务执行，直接传入带有 assistant 角色的消息会被 Prism 忽略或导致上下文丢失。
        因此，对于多轮对话，需要将历史对话记录合并注入到当前请求的 Prompt 中。
        """
        if not messages:
            return []

        def get_text(content: Any) -> str:
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                return "\n".join(text_parts)
            return str(content or "")

        if len(messages) == 1:
            content_str = get_text(messages[0].get("content", ""))
            return [{
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": content_str}]
            }]

        history_lines = []
        for m in messages[:-1]:
            role = m.get("role", "user").lower()
            c_str = get_text(m.get("content", "")).strip()
            if not c_str:
                continue
            if role == "system":
                history_lines.append(f"[System Instruction]\n{c_str}")
            elif role == "assistant":
                history_lines.append(f"[Assistant]\n{c_str}")
            else:
                history_lines.append(f"[User]\n{c_str}")

        last_content = get_text(messages[-1].get("content", ""))
        if history_lines:
            combined_prompt = (
                "[Conversation History]\n"
                + "\n\n".join(history_lines)
                + "\n\n[Current User Message]\n"
                + last_content
            )
        else:
            combined_prompt = last_content

        return [{
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": combined_prompt}]
        }]

    async def start_inference(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        reasoning_effort: Optional[str] = None
    ) -> Dict[str, Any]:
        """发起 AI 推理任务 (POST /api/llm/response_with_tools_start)"""
        url = f"{self.base_url}/api/llm/response_with_tools_start"
        input_items = self._convert_messages(messages)
        mapped_model = map_model(model)

        sb_url, sb_token = await self.ensure_sandbox_synced(client, project_id)

        user_id = self._cached_user_id or str(uuid.uuid4())
        if not reasoning_effort:
            model_lower = (model or "").lower()
            if "xhigh" in model_lower:
                eff = "xhigh"
            elif "low" in model_lower:
                eff = "low"
            elif "preview" in model_lower or "medium" in model_lower:
                eff = "medium"
            else:
                eff = "high"
        else:
            eff = reasoning_effort.strip().lower()

        if eff not in ("low", "medium", "high", "xhigh"):
            eff = "high"

        payload = {
            "input": input_items,
            "metadata": {
                "projectId": project_id,
                "userId": user_id,
                "model": mapped_model,
                "reasoning_effort": eff,
                "frontend_origin": self.base_url,
                "sandbox_url": sb_url,
                "sandbox_token": sb_token
            },
            "conversationId": None,
            "previousResponseId": None
        }

        resp = await client.post(url, json=payload, headers=self._get_headers(), timeout=settings.HTTP_TIMEOUT_SECONDS)
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"Prism start inference failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        logger.info(f"Prism inference started response keys: {list(data.keys())}, status: {data.get('status')}")
        if data.get("response", {}).get("status") == "error":
            logger.error(f"Prism response returned error: {data.get('response', {}).get('payload')}")
        return data

    async def poll_status(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        request_id: str,
        turn_state: Any
    ) -> Dict[str, Any]:
        """查询任务状态 (POST /api/llm/response_with_tools_status)"""
        url = f"{self.base_url}/api/llm/response_with_tools_status"
        payload = {
            "request_id": request_id,
            "turn_state": turn_state
        }
        resp = await client.post(url, json=payload, headers=self._get_headers(), timeout=30.0)
        if resp.status_code != 200:
            raise RuntimeError(f"Prism poll status failed ({resp.status_code}): {resp.text}")
        return resp.json()

