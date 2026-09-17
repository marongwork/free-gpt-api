import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from app.config import settings
from app.prism_client import PrismClient
from app.schemas import (
    ChatCompletionChunk,
    ChatCompletionResponse,
    ChatCompletionChoice,
    AssistantResponseMessage,
    ChatCompletionStreamChoice,
    DeltaMessage,
    UsageInfo,
)

logger = logging.getLogger("sse_adapter")


def _extract_output_text(resp_obj: Dict[str, Any]) -> str:
    """从 Prism response 对象提取最终助手回答"""
    if not isinstance(resp_obj, dict):
        return ""
    if resp_obj.get("status") == "success":
        payload = resp_obj.get("payload", {})
        outputs = payload.get("output", [])
        text_parts = []
        for out in outputs:
            for c in out.get("content", []):
                if isinstance(c, dict) and c.get("text"):
                    text_parts.append(c["text"])
                elif isinstance(c, str):
                    text_parts.append(c)
        return "\n".join(text_parts)
    elif resp_obj.get("status") == "error":
        err = resp_obj.get("payload", {})
        return f"Error: {err.get('message', 'Unknown Prism error')}"
    return ""


async def stream_chat_completion(
    prism_client: PrismClient,
    messages: List[Dict[str, Any]],
    model: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    reasoning_effort: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """生成符合 OpenAI SSE 规范的流式数据"""
    completion_id = f"chatcmpl-prism-{uuid.uuid4().hex[:12]}"
    created_time = int(time.time())

    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
        # 1. 获取工作空间项目
        project_id = await prism_client.get_or_create_project(client)

        # 2. 发起推理请求
        task_info = await prism_client.start_inference(
            client=client,
            project_id=project_id,
            messages=messages,
            model=model,
            tools=tools,
            reasoning_effort=reasoning_effort
        )

        # 发送起始角色块
        initial_chunk = ChatCompletionChunk(
            id=completion_id,
            created=created_time,
            model=model,
            choices=[
                ChatCompletionStreamChoice(
                    index=0,
                    delta=DeltaMessage(role="assistant"),
                    finish_reason=None
                )
            ]
        )
        yield f"data: {initial_chunk.model_dump_json()}\n\n"

        status = task_info.get("status")
        if status == "completed":
            resp_obj = task_info.get("response", {})
            content = _extract_output_text(resp_obj)
            if content:
                chunk = ChatCompletionChunk(
                    id=completion_id,
                    created=created_time,
                    model=model,
                    choices=[ChatCompletionStreamChoice(index=0, delta=DeltaMessage(content=content), finish_reason=None)]
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
        elif status == "started":
            request_id = task_info["request_id"]
            turn_state = task_info.get("turn_state")
            seen_reasoning = set()
            poll_interval = max(settings.POLL_INTERVAL_MS / 1000.0, 2.0)

            for attempt in range(settings.POLL_MAX_RETRIES):
                await asyncio.sleep(poll_interval)
                try:
                    poll_data = await prism_client.poll_status(client, project_id, request_id, turn_state)
                except Exception as e:
                    logger.warning(f"Poll attempt {attempt} failed: {e}")
                    continue

                curr_status = poll_data.get("status")
                if curr_status == "pending":
                    turn_state = poll_data.get("turn_state", turn_state)
                    # 增量提取思考过程
                    progress = poll_data.get("progress", {})
                    if isinstance(progress, dict):
                        summaries = progress.get("reasoningSummaries", [])
                        for s in summaries:
                            text = s.get("text", "")
                            if text and text not in seen_reasoning:
                                seen_reasoning.add(text)
                                chunk = ChatCompletionChunk(
                                    id=completion_id,
                                    created=created_time,
                                    model=model,
                                    choices=[ChatCompletionStreamChoice(index=0, delta=DeltaMessage(reasoning_content=text + "\n"), finish_reason=None)]
                                )
                                yield f"data: {chunk.model_dump_json()}\n\n"
                elif curr_status == "completed":
                    resp_obj = poll_data.get("response", {})
                    content = _extract_output_text(resp_obj)
                    if content:
                        chunk = ChatCompletionChunk(
                            id=completion_id,
                            created=created_time,
                            model=model,
                            choices=[ChatCompletionStreamChoice(index=0, delta=DeltaMessage(content=content), finish_reason=None)]
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"
                    break
                else:
                    logger.warning(f"Unknown poll status: {curr_status}")
                    break

        # 发送结束块
        final_chunk = ChatCompletionChunk(
            id=completion_id,
            created=created_time,
            model=model,
            choices=[
                ChatCompletionStreamChoice(
                    index=0,
                    delta=DeltaMessage(),
                    finish_reason="stop"
                )
            ]
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"


async def non_stream_chat_completion(
    prism_client: PrismClient,
    messages: List[Dict[str, Any]],
    model: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    reasoning_effort: Optional[str] = None
) -> ChatCompletionResponse:
    """非流式聚合返回"""
    completion_id = f"chatcmpl-prism-{uuid.uuid4().hex[:12]}"
    created_time = int(time.time())
    full_content = ""
    full_thought = ""

    async for sse_item in stream_chat_completion(
        prism_client=prism_client,
        messages=messages,
        model=model,
        tools=tools,
        reasoning_effort=reasoning_effort
    ):
        if not sse_item.startswith("data: ") or sse_item.strip() == "data: [DONE]":
            continue
        try:
            chunk_json = json.loads(sse_item[6:])
            choices = chunk_json.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                if "content" in delta and delta["content"]:
                    full_content += delta["content"]
                if "reasoning_content" in delta and delta["reasoning_content"]:
                    full_thought += delta["reasoning_content"]
        except Exception:
            pass

    return ChatCompletionResponse(
        id=completion_id,
        created=created_time,
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=AssistantResponseMessage(
                    role="assistant",
                    content=full_content,
                    reasoning_content=full_thought if full_thought else None
                ),
                finish_reason="stop"
            )
        ],
        usage=UsageInfo(
            prompt_tokens=len(str(messages)) // 4,
            completion_tokens=(len(full_content) + len(full_thought)) // 4,
            total_tokens=(len(str(messages)) + len(full_content) + len(full_thought)) // 4
        )
    )

