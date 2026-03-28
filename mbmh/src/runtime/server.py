"""
Runtime server orchestrator.

Ties together:
  - model/tokenizer loading from a runtime bundle
  - agent registry loading
  - API key auth initialisation
  - session store
  - FastAPI app creation + uvicorn launch
"""

import logging

from .config import RuntimeConfig
from .auth import init_auth
from .generation import generate_from_messages
from .openai_compat import create_openai_app
from .session_store import SessionStore
from .safety import is_safe_tool_request

from ..agents.task_router import load_agents
from ..agents.memory import SessionMemory

logger = logging.getLogger(__name__)


def _apply_hf_hub_timeouts(seconds: int) -> None:
    """Raise Hugging Face Hub HTTP timeouts before importing transformers/huggingface_hub."""
    import os

    s = str(max(30, int(seconds)))
    # HEAD/metadata (etag) and file downloads both default to 10s and cause ReadTimeout on slow links.
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", s)
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", s)


def create_and_run_server(config: RuntimeConfig, model=None, tokenizer=None):
    """Build everything and start serving.

    Parameters
    ----------
    config : RuntimeConfig
    model : optional pre-loaded model (if None, loads from bundle)
    tokenizer : optional pre-loaded tokenizer
    """
    import uvicorn

    # ── 1. Auth ────────────────────────────────────────────────────────
    init_auth(config.api_keys_path)
    logger.info("Auth initialised from %s", config.api_keys_path)

    # ── 2. Agents ─────────────────────────────────────────────────────
    agent_registry = load_agents(config.agents_dir)
    logger.info("Loaded %d agents: %s", len(agent_registry), list(agent_registry.keys()))

    # ── 3. Model (optional – may already be loaded by caller) ─────────
    if model is not None and tokenizer is not None:
        device = str(model.device) if hasattr(model, "device") else "cpu"
        logger.info("Using pre-loaded model on %s", device)
    elif getattr(config, "base_model", None):
        logger.info("Loading HF model from base_model=%r", config.base_model)
        _apply_hf_hub_timeouts(getattr(config, "hf_hub_timeout_seconds", 300))
        import os
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

        weight_dtype = torch.float16 if device != "cpu" else torch.float32
        try:
            logger.info(
                "Hub timeouts: HF_HUB_ETAG_TIMEOUT=%s HF_HUB_DOWNLOAD_TIMEOUT=%s (env or config; set before first hub use)",
                os.environ.get("HF_HUB_ETAG_TIMEOUT", "10"),
                os.environ.get("HF_HUB_DOWNLOAD_TIMEOUT", "10"),
            )
            logger.info("Loading tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(config.base_model)
            logger.info("Loading weights to %s (dtype=%s)...", device, weight_dtype)
            model = AutoModelForCausalLM.from_pretrained(
                config.base_model,
                dtype=weight_dtype,
                low_cpu_mem_usage=True,
            ).to(device)
            logger.info("Model loaded successfully.")
        except Exception:
            logger.exception(
                "Failed to load base_model %r; serving in agent-only mode",
                config.base_model,
            )
            model, tokenizer = None, None
    else:
        logger.info(
            "No model pre-loaded and no base_model in config "
            "(set base_model in runtime YAML to enable local inference). "
            "Serving in agent-only mode."
        )

    # ── 4. Generation function ────────────────────────────────────────
    def _generate(messages, *, temperature=0.7, max_tokens=256, stream=False):
        if model is None or tokenizer is None:
            msg = "[No model loaded — server running in agent-only mode]"
            return [msg] if stream else msg
            
        return generate_from_messages(
            model, tokenizer, messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream
        )

    # ── 5. Session store ──────────────────────────────────────────────
    session_store = SessionStore()
    memory = SessionMemory(session_store)

    # ── 6. Build app ──────────────────────────────────────────────────
    app = create_openai_app(
        agent_registry=agent_registry,
        generate_fn=_generate,
        session_memory=memory,
        tools={},  # Tools loaded separately when enabled
        safety_check=is_safe_tool_request,
    )

    logger.info("Starting server on %s:%s", config.host, config.port)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


def start_server(config: RuntimeConfig, bundle_id: str):
    """Legacy entry used by serve_local.py — wires through to the real server."""
    if config.server_mode == "openai_compatible":
        config.bundle_id = bundle_id
        create_and_run_server(config)
    else:
        # Direct / non-API mode: keep simple
        print(f"Starting direct inference loop on bundle {bundle_id}")
        print("Use --config configs/runtime/openai-compatible.yaml for the API server.")
