import json
import os
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.schemas import ChatCompletionRequest
from backend.constants import PROMPT_TEMPLATE
from backend.tools import TOOLS, execute_tool_call

MODEL = 'gpt-5.4'
TEMPERATURE = 0.2
TOP_P = 0.8
DEFAULT_RETRIEVED_CONTEXT = "No additional context was retrieved."
MAX_TOOL_ROUNDS = 5
MAX_CONVERSATION_HISTORY_CHARS = 12_000
MAX_SUMMARIZED_USER_MESSAGES = 8
MAX_SUMMARIZED_MESSAGE_CHARS = 240
MAX_SUMMARIZED_HISTORY_CHARS = 1_800


def _stringify_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _truncate_text(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _summarize_prior_user_messages(prior_user_messages: list[str]) -> str:
    if not prior_user_messages:
        return "No earlier user messages."

    selected_messages = prior_user_messages[-MAX_SUMMARIZED_USER_MESSAGES:]
    omitted_count = len(prior_user_messages) - len(selected_messages)
    start_index = len(prior_user_messages) - len(selected_messages) + 1

    summary_lines = [
        f"- User message {index}: "
        f"{_truncate_text(message, MAX_SUMMARIZED_MESSAGE_CHARS)}"
        for index, message in enumerate(selected_messages, start=start_index)
    ]
    summary = "\n".join(summary_lines)

    if len(summary) > MAX_SUMMARIZED_HISTORY_CHARS:
        summary = _truncate_text(summary, MAX_SUMMARIZED_HISTORY_CHARS)

    if omitted_count > 0:
        return f"{omitted_count} earlier user messages were omitted for brevity.\n{summary}"

    return summary


async def _resolve_tool_messages(
    client: AsyncOpenAI,
    request_kwargs: dict[str, Any],
) -> dict[str, Any]:
    tool_request_kwargs = dict(request_kwargs)
    tool_request_kwargs["stream"] = False
    tool_request_kwargs["tools"] = TOOLS

    response = await client.chat.completions.create(**tool_request_kwargs)

    for _ in range(MAX_TOOL_ROUNDS):
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return tool_request_kwargs

        tool_request_kwargs["messages"].append(message.model_dump(exclude_none=True))
        for tool_call in tool_calls:
            tool_result = execute_tool_call(
                tool_name=tool_call.function.name,
                arguments_json=tool_call.function.arguments,
            )
            tool_request_kwargs["messages"].append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

        response = await client.chat.completions.create(**tool_request_kwargs)

    return tool_request_kwargs

async def get_chat_completion(payload: ChatCompletionRequest) -> Any:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    metadata = payload.metadata or {}
    context = metadata.get("context") or metadata.get("retrieved_context")
    rdd_pooled_context = metadata.get("rdd_pooled_context", DEFAULT_RETRIEVED_CONTEXT)
    rdd_school_context = metadata.get("rdd_school_context", DEFAULT_RETRIEVED_CONTEXT)
    did_pooled_context = metadata.get("did_pooled_context", DEFAULT_RETRIEVED_CONTEXT)
    did_school_context = metadata.get("did_school_context", DEFAULT_RETRIEVED_CONTEXT)
    supporting_context = (
        ""
        if context is None
        else context
        if isinstance(context, str)
        else json.dumps(context, ensure_ascii=False)
    )

    history_lines: list[str] = []
    prior_user_messages: list[str] = []
    latest_user_message = ""
    latest_user_payload: dict[str, Any] | None = None
    for message in payload.messages:
        content = _stringify_message_content(message.content)
        history_lines.append(f"{message.role}: {content}")
        if message.role == "user":
            if latest_user_message:
                prior_user_messages.append(latest_user_message)
            latest_user_message = content
            latest_user_payload = message.model_dump(exclude_none=True)

    # TODO: Add retrieval or routing logic here based on latest_user_message.
    conversation_history = "\n".join(history_lines)
    effective_messages = [
        message.model_dump(exclude_none=True) for message in payload.messages
    ]

    if (
        len(conversation_history) > MAX_CONVERSATION_HISTORY_CHARS
        and latest_user_message
        and latest_user_payload is not None
    ):
        summarized_prior_user_messages = _summarize_prior_user_messages(
            prior_user_messages
        )
        conversation_history = (
            "Earlier user messages were condensed because the conversation "
            "history exceeded the context budget.\n"
            f"{summarized_prior_user_messages}\n\n"
            f"Latest user message:\n{latest_user_message}"
        )
        effective_messages = [latest_user_payload]

    upstream_messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": PROMPT_TEMPLATE.format(
                retrieved_context=supporting_context or DEFAULT_RETRIEVED_CONTEXT,
                conversation_history=conversation_history,
                rdd_pooled_context=(
                    rdd_pooled_context
                    if isinstance(rdd_pooled_context, str)
                    else json.dumps(rdd_pooled_context, ensure_ascii=False)
                ),
                rdd_school_context=(
                    rdd_school_context
                    if isinstance(rdd_school_context, str)
                    else json.dumps(rdd_school_context, ensure_ascii=False)
                ),
                did_pooled_context=(
                    did_pooled_context
                    if isinstance(did_pooled_context, str)
                    else json.dumps(did_pooled_context, ensure_ascii=False)
                ),
                did_school_context=(
                    did_school_context
                    if isinstance(did_school_context, str)
                    else json.dumps(did_school_context, ensure_ascii=False)
                ),
            ),
        }
    ]
    upstream_messages.extend(effective_messages)

    request_kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": upstream_messages,
        "stream": payload.stream,
        "temperature": (
            payload.temperature if payload.temperature is not None else TEMPERATURE
        ),
        "top_p": payload.top_p if payload.top_p is not None else TOP_P,
    }
    if payload.max_tokens is not None:
        request_kwargs["max_tokens"] = payload.max_tokens
    if payload.stop is not None:
        request_kwargs["stop"] = payload.stop
    if payload.user is not None:
        request_kwargs["user"] = payload.user
    client = AsyncOpenAI(api_key=api_key)
    resolved_request_kwargs = await _resolve_tool_messages(client, request_kwargs)

    final_request_kwargs = dict(resolved_request_kwargs)
    final_request_kwargs.pop("tools", None)
    final_request_kwargs["stream"] = payload.stream

    if payload.stream:
        final_request_kwargs["stream_options"] = {"include_usage": True}
    else:
        final_request_kwargs.pop("stream_options", None)

    return await client.chat.completions.create(**final_request_kwargs)


async def stream_chat_chunks(stream: Any) -> AsyncIterator[str]:
    async for chunk in stream:
        payload = chunk.model_dump(exclude_none=True)
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
