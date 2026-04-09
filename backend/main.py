from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAIError

from backend.helper import MODEL, get_chat_completion, stream_chat_chunks
from backend.schemas import ChatCompletionRequest


app = FastAPI(
    title="Open WebUI Companion Backend",
    version="0.1.0",
    description="A FastAPI proxy that fetches context and forwards chat completions to OpenAI.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/models", response_model=None)
async def list_models() -> Response:
    return JSONResponse(
        content={
            "object": "list",
            "data": [
                {
                    "id": 'DieDieMustOneKM',
                    "object": "model",
                    "created": 0,
                    "owned_by": "openai-proxy",
                }
            ],
        }
    )


@app.post(
    "/v1/chat/completions",
    description="Proxy endpoint for chat completions with context retrieval.",
    response_model=None,
)
async def chat_completions(payload: ChatCompletionRequest) -> Response:
    try:
        completion = await get_chat_completion(payload)

        if payload.stream:
            return StreamingResponse(
                stream_chat_chunks(completion),
                media_type="text/event-stream",
            )

        return JSONResponse(content=completion.model_dump(exclude_none=True))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI API error ({type(exc).__name__}): {exc}",
        ) from exc
