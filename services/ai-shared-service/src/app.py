"""Minimal AI Stack service exposing LangChain/Haystack endpoints.

This is a scaffold to host simple chains/pipelines and route to the existing
worker via OpenAI-compatible API (OPENAI_BASE_URL)."""

import os
from typing import Any, Dict

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI

logger = structlog.get_logger()

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://worker.local:8000/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "not-set")

app = FastAPI(title="AI Stack", version="0.1.0")


class PromptRequest(BaseModel):
    prompt: str
    model: str = "mistralai/Mistral-7B-Instruct-v0.3"


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "openai_base_url": OPENAI_BASE_URL,
    }


@app.post("/llm/prompt")
async def llm_prompt(req: PromptRequest) -> Dict[str, Any]:
    try:
        client = AsyncOpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model=req.model,
            messages=[{"role": "user", "content": req.prompt}],
            temperature=0.1,
        )
        return {
            "model": req.model,
            "output": resp.choices[0].message.content if resp.choices else "",
        }
    except Exception as e:  # pragma: no cover - simple scaffold
        logger.error("llm_prompt_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
