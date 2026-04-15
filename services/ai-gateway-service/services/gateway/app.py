import os
import re
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import hashlib
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, Depends, Header, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import jwt

# Configure logging
import logging.config
import sys

# JSON logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_JSON_LOGGING = os.getenv("ENABLE_JSON_LOGGING", "true").lower() == "true"


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": "gateway",
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from log record
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "ip_address"):
            log_entry["ip_address"] = record.ip_address
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "endpoint"):
            log_entry["endpoint"] = record.endpoint
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "event_type"):
            log_entry["event_type"] = record.event_type
        if hasattr(record, "metadata"):
            log_entry["metadata"] = record.metadata

        return json.dumps(log_entry)


# Configure logging handlers
handlers = []

# File handler
try:
    file_handler = logging.FileHandler("/logs/gateway.log", mode="a")
except (FileNotFoundError, PermissionError, OSError):
    file_handler = logging.FileHandler("gateway.log", mode="a")

if ENABLE_JSON_LOGGING:
    file_handler.setFormatter(JSONFormatter())
else:
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
handlers.append(file_handler)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
if ENABLE_JSON_LOGGING:
    console_handler.setFormatter(JSONFormatter())
else:
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
handlers.append(console_handler)

# Configure root logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()), handlers=handlers, force=True
)
logger = logging.getLogger(__name__)

# Performance settings
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
REQUESTS_POOL_CONNECTIONS = int(os.getenv("REQUESTS_POOL_CONNECTIONS", "10"))
REQUESTS_POOL_MAXSIZE = int(os.getenv("REQUESTS_POOL_MAXSIZE", "50"))

# TypeScript agent-platform is the default orchestrator (Python retired from default deploy).
ORCHESTRATOR_BASE_URL = os.getenv(
    "ORCHESTRATOR_URL", "http://wrkhrs-agent-platform:8000"
).rstrip("/")

# Shared HTTP session to the orchestrator for connection pooling and retries
ORCH_SESSION = requests.Session()
_retry = Retry(total=2, backoff_factor=0.3, status_forcelist=(502, 503, 504))
ORCH_SESSION.mount(
    "http://",
    HTTPAdapter(
        pool_connections=REQUESTS_POOL_CONNECTIONS,
        pool_maxsize=REQUESTS_POOL_MAXSIZE,
        max_retries=_retry,
    ),
)


def get_secret(name: str, default: str = "") -> str:
    """Read a secret from env or a file referenced by NAME_FILE."""
    file_path = os.getenv(f"{name}_FILE")
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return os.getenv(name, default)


# Authentication configuration (support *_FILE secret mounts)
API_KEY_SECRET = get_secret("API_KEY_SECRET", "default-secret-change-in-production")
JWT_SECRET_KEY = get_secret("JWT_SECRET_KEY", "default-jwt-secret-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
ENABLE_AUTH = os.getenv("ENABLE_AUTHENTICATION", "true").lower() == "true"

# Rate limiting storage
request_counts = defaultdict(list)
security = HTTPBearer(auto_error=False)

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Lifespan hook replacing deprecated on_event handlers."""
    if os.getenv("WRKHRS_DISABLE_MODEL_LOAD", "").lower() in ("1", "true", "yes"):
        logger.info("Skipping embedding load (WRKHRS_DISABLE_MODEL_LOAD)")
        yield
        return
    load_models()
    yield


# Initialize FastAPI app with comprehensive OpenAPI documentation
api = FastAPI(
    title="AI Stack Gateway",
    description="""
    # AI Stack Gateway API
    
    The AI Stack Gateway serves as the main entry point for the AI stack, providing:
    
    * **Authentication & Authorization**: API key and JWT token authentication
    * **Rate Limiting**: Configurable request rate limiting per client
    * **Domain Weighting**: Intelligent routing based on chemistry, mechanical, and materials domains
    * **Non-generative Conditioning**: Constraint application and unit normalization
    * **Request Orchestration**: Coordinates requests across multiple AI services
    
    ## Authentication
    
    The API supports two authentication methods:
    
    ### API Key Authentication
    Include your API key in the `X-API-Key` header:
    ```
    X-API-Key: your-api-key-here
    ```
    
    ### JWT Token Authentication  
    Include your JWT token in the `Authorization` header:
    ```
    Authorization: Bearer your-jwt-token-here
    ```
    
    ## Rate Limiting
    
    Requests are limited to 60 per minute per IP address by default. 
    Rate limit headers are included in responses:
    - `X-RateLimit-Limit`: Maximum requests per minute
    - `X-RateLimit-Remaining`: Remaining requests in current window
    - `X-RateLimit-Reset`: Time when rate limit resets
    
    ## Domain Weighting
    
    The gateway automatically detects domain relevance for:
    - **Chemistry**: Molecular formulas, reactions, pH, concentrations
    - **Mechanical**: Stress, strain, forces, beam analysis
    - **Materials**: Properties, compositions, hardness, thermal characteristics
    
    ## Error Responses
    
    The API returns structured error responses:
    ```json
    {
        "detail": "Error description",
        "error_code": "AUTH_REQUIRED",
        "timestamp": "2023-09-21T18:51:00Z"
    }
    ```
    """,
    version="1.0.0",
    contact={
        "name": "AI Stack Team",
        "email": "support@aistack.local",
        "url": "https://github.com/aistack/gateway",
    },
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    servers=[
        {"url": "http://localhost:8080", "description": "Development server"},
        {"url": "https://api.aistack.local", "description": "Production server"},
    ],
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Authentication and authorization endpoints",
        },
        {"name": "Chat", "description": "OpenAI-compatible chat completion endpoints"},
        {"name": "Health", "description": "Service health and status endpoints"},
        {
            "name": "Processing",
            "description": "Text processing and domain analysis endpoints",
        },
    ],
    lifespan=lifespan,
)

# Add CORS middleware
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
embedding_model = None
domain_classifier = None


class ChatRequest(BaseModel):
    # OpenAI-compatible clients may send rich message objects (tool calls, arrays, null content).
    # Keep this schema permissive so local gateways can serve as a drop-in baseUrl for agents.
    messages: List[Dict[str, Any]]
    model: Optional[str] = "default"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    stream: Optional[bool] = None


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


class DomainWeights(BaseModel):
    chemistry: float = 0.0
    mechanical: float = 0.0
    materials: float = 0.0


class ProcessedPrompt(BaseModel):
    original_prompt: str
    domain_weights: DomainWeights
    extracted_units: List[str]
    constraints: List[str]
    weighted_evidence: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# Domain classification patterns
DOMAIN_PATTERNS = {
    "chemistry": [
        r"\b(?:mol|molecular|atom|bond|reaction|catalyst|pH|concentration|solvent)\b",
        r"\b(?:organic|inorganic|polymer|synthesis|crystalline)\b",
        r"\b(?:H2O|CO2|NaCl|C6H12O6|chemical|formula)\b",
    ],
    "mechanical": [
        r"\b(?:force|stress|strain|torque|pressure|tension|compression)\b",
        r"\b(?:beam|shaft|gear|bearing|joint|mechanism|machine)\b",
        r"\b(?:N|Pa|MPa|GPa|kN|newton|pascal)\b",
    ],
    "materials": [
        r"\b(?:steel|aluminum|composite|ceramic|polymer|metal|alloy)\b",
        r"\b(?:hardness|ductility|brittleness|elasticity|plasticity)\b",
        r"\b(?:microstructure|grain|phase|crystal|defect)\b",
    ],
}

# SI unit patterns
SI_UNIT_PATTERNS = [
    r"\b\d+\.?\d*\s*(?:m|kg|s|A|K|mol|cd)\b",  # Base SI units
    r"\b\d+\.?\d*\s*(?:N|Pa|J|W|V|Ω|Hz)\b",  # Derived SI units
    r"\b\d+\.?\d*\s*(?:mm|cm|km|mg|g|kg)\b",  # Common prefixes
    r"\b\d+\.?\d*\s*(?:MPa|GPa|kN|mN|mA|kA)\b",  # Engineering units
]


# Authentication functions
def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    if not ENABLE_AUTH:
        return True

    current_time = time.time()
    minute_ago = current_time - 60

    # Clean old requests
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip] if req_time > minute_ago
    ]

    # Check if under limit
    if len(request_counts[client_ip]) >= RATE_LIMIT_RPM:
        return False

    # Add current request
    request_counts[client_ip].append(current_time)
    return True


def validate_api_key(api_key: str) -> bool:
    """Validate API key using simple hash comparison"""
    if not api_key:
        return False

    # Simple hash-based validation (in production, use proper key management)
    expected_hash = hashlib.sha256(API_KEY_SECRET.encode()).hexdigest()
    provided_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return expected_hash == provided_hash


def create_jwt_token(data: dict) -> str:
    """Create JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Optional[dict]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT token")
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    x_api_key: Optional[str] = Header(None),
):
    """Authentication dependency"""
    if not ENABLE_AUTH:
        return {"authenticated": True, "method": "disabled"}

    client_ip = request.client.host

    # Check rate limit
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Try API key authentication first
    if x_api_key and validate_api_key(x_api_key):
        logger.info(
            "API key authentication successful",
            extra={
                "event_type": "authentication",
                "ip_address": client_ip,
                "method": "api_key",
                "endpoint": request.url.path,
                "metadata": {"success": True},
            },
        )
        return {"authenticated": True, "method": "api_key", "ip": client_ip}

    # Try JWT authentication
    if credentials and credentials.credentials:
        payload = verify_jwt_token(credentials.credentials)
        if payload:
            logger.info(
                "JWT authentication successful",
                extra={
                    "event_type": "authentication",
                    "ip_address": client_ip,
                    "method": "jwt",
                    "user_id": payload.get("sub"),
                    "endpoint": request.url.path,
                    "metadata": {"success": True, "token_exp": payload.get("exp")},
                },
            )
            return {
                "authenticated": True,
                "method": "jwt",
                "payload": payload,
                "ip": client_ip,
            }

    # Authentication failed
    logger.warning(
        "Authentication failed",
        extra={
            "event_type": "authentication",
            "ip_address": client_ip,
            "endpoint": request.url.path,
            "metadata": {
                "success": False,
                "api_key_provided": bool(x_api_key),
                "jwt_provided": bool(credentials and credentials.credentials),
            },
        },
    )
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide X-API-Key header or Bearer token.",
    )


def load_models():
    """Load embedding model and initialize domain classifier"""
    global embedding_model, domain_classifier
    try:
        from sentence_transformers import SentenceTransformer

        embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        logger.info("Embedding model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        embedding_model = None


def extract_domain_weights(text: str) -> DomainWeights:
    """Extract domain weights using pattern matching and embeddings"""
    weights = DomainWeights()

    # Pattern-based scoring
    for domain, patterns in DOMAIN_PATTERNS.items():
        score = 0.0
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            score += len(matches) * 0.1

        # Normalize and cap at 1.0
        score = min(score, 1.0)
        setattr(weights, domain, score)

    return weights


def extract_units(text: str) -> List[str]:
    """Extract units from text for SI normalization"""
    units = []
    for pattern in SI_UNIT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        units.extend(matches)
    return list(set(units))  # Remove duplicates


def extract_constraints(text: str) -> List[str]:
    """Extract safety and operational constraints"""
    constraint_patterns = [
        r"\b(?:safety|hazard|toxic|flammable|corrosive|dangerous)\b",
        r"\b(?:temperature limit|pressure limit|max|min|range)\b",
        r"\b(?:standard|specification|code|regulation|requirement)\b",
    ]

    constraints = []
    for pattern in constraint_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        constraints.extend(matches)

    return list(set(constraints))


async def get_weighted_evidence(prompt: str, weights: DomainWeights) -> str:
    """Get weighted evidence from RAG system"""
    try:
        rag_url = "http://rag-api:8000/search"
        payload = {"query": prompt, "domain_weights": weights.model_dump(), "k": 5}

        response = requests.post(rag_url, json=payload, timeout=10)
        if response.status_code == 200:
            evidence = response.json().get("evidence", "")
            return evidence
        else:
            logger.warning(f"RAG service returned {response.status_code}")
            return ""
    except Exception as e:
        logger.error(f"Failed to get weighted evidence: {e}")
        return ""


@api.post(
    "/auth/login",
    response_model=LoginResponse,
    tags=["Authentication"],
    summary="Login to generate JWT token",
    description="""
         Generate a JWT token for API authentication.
         
         **Authentication Method**: None required (this is the login endpoint)
         
         **Request Body**: 
         - `username`: User identifier
         - `password`: User password (should match API_KEY_SECRET for demo)
         
         **Response**:
         - `access_token`: JWT token for subsequent requests
         - `token_type`: Always "bearer"
         - `expires_in`: Token expiration time in seconds
         
         **Example Usage**:
         ```bash
         curl -X POST "http://localhost:8080/auth/login" \\
              -H "Content-Type: application/json" \\
              -d '{"username": "admin", "password": "your-api-secret"}'
         ```
         """,
)
async def login(request: LoginRequest):
    """Login endpoint to generate JWT token"""
    # Simple credential validation (in production, use proper user management)
    if request.username == "admin" and request.password == API_KEY_SECRET:
        token_data = {"sub": request.username, "username": request.username}
        access_token = create_jwt_token(token_data)
        return LoginResponse(
            access_token=access_token, expires_in=JWT_EXPIRATION_HOURS * 3600
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@api.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "embedding_model_loaded": embedding_model is not None,
        "authentication_enabled": ENABLE_AUTH,
    }


@api.get("/v1/models")
async def list_models(current_user: dict = Depends(get_current_user)):
    """OpenAI-compatible model listing.

    The Birtha API health check and OpenClaw both call GET /v1/models to confirm the
    configured OpenAI-compatible base URL is reachable. The gateway is an adapter
    around an orchestrator backend, so this list is descriptive rather than exhaustive.
    """
    # IMPORTANT: Prefer a *real* model id here so OpenAI-compatible clients don't
    # turn around and request a sentinel like "wrkhrs-gateway", which the TS
    # orchestrator may treat as an explicit model override and route incorrectly.
    #
    # Precedence:
    # - Explicit gateway overrides: DEFAULT_LLM_MODEL / LLM_MODEL
    # - Compose-local inference lane hints: OLLAMA_MODEL (host Ollama) / VLLM_MODEL (GPU worker)
    # - Fallback sentinel (should be avoided in dev)
    model_id = (
        os.getenv("DEFAULT_LLM_MODEL")
        or os.getenv("LLM_MODEL")
        or os.getenv("OLLAMA_MODEL")
        or os.getenv("VLLM_MODEL")
        or "wrkhrs-gateway"
    )
    now = int(datetime.utcnow().timestamp())
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": now,
                "owned_by": "wrkhrs-gateway",
            }
        ],
    }


@api.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    chat_request: ChatRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
):
    """OpenAI-compatible chat completions endpoint with non-generative conditioning"""
    try:
        def _coerce_content(raw: Any) -> str:
            if raw is None:
                return ""
            if isinstance(raw, str):
                return raw
            # OpenAI-compatible multimodal messages can send content as an array of parts.
            # Keep only text-ish parts so downstream regex/domain parsing stays stable.
            if isinstance(raw, list):
                parts: list[str] = []
                for part in raw:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict):
                        if part.get("type") == "text" and isinstance(part.get("text"), str):
                            parts.append(part["text"])
                        elif isinstance(part.get("content"), str):
                            parts.append(part["content"])
                return "\n".join([p for p in parts if p])
            if isinstance(raw, dict):
                if raw.get("type") == "text" and isinstance(raw.get("text"), str):
                    return raw["text"]
                if isinstance(raw.get("content"), str):
                    return raw["content"]
            return str(raw)

        # Extract the user's prompt
        user_message = None
        for msg in chat_request.messages:
            if msg.get("role") == "user":
                user_message = _coerce_content(msg.get("content"))
                break

        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        # Process prompt with non-generative conditioning
        processed = await process_prompt(user_message)

        # Forward to orchestrator with enhanced context
        # The TS agent-platform orchestrator expects `content` to be a string.
        # OpenAI-compatible clients (incl. OpenClaw) may send `content` as an array of parts
        # (multimodal) or other rich shapes. Coerce *all* message contents before forwarding.
        enhanced_messages: list[dict[str, Any]] = []
        for msg in chat_request.messages:
            coerced = dict(msg)
            coerced["content"] = _coerce_content(msg.get("content"))
            enhanced_messages.append(coerced)

        # Add domain context and evidence without changing the original prompt
        if processed.weighted_evidence:
            system_context = f"""
Domain Analysis: Chemistry={processed.domain_weights.chemistry:.2f}, Mechanical={processed.domain_weights.mechanical:.2f}, Materials={processed.domain_weights.materials:.2f}
Relevant Evidence: {processed.weighted_evidence}
Units Found: {', '.join(processed.extracted_units)}
Constraints: {', '.join(processed.constraints)}

Please respond with SI units and consider the safety constraints mentioned.
"""
            enhanced_messages.insert(0, {"role": "system", "content": system_context})

        # Forward to orchestrator (Python or TS agent-platform)
        orchestrator_url = f"{ORCHESTRATOR_BASE_URL}/chat"
        # If the client passed back a sentinel "model" we advertised for reachability,
        # drop it so the orchestrator can choose the correct local-worker routing.
        model_override = chat_request.model
        # Many OpenAI-compatible clients send model="default" when they want the server-side default.
        # Treat that like "no override" so the TS orchestrator can select its configured local-worker route.
        if isinstance(model_override, str) and model_override.strip().lower() in {
            "wrkhrs-gateway",
            "orchestrator",
            "default",
        }:
            model_override = None

        # NOTE: the TS orchestrator schema treats `model` as optional, but rejects explicit null.
        # Only include routing fields when they are non-null.
        orchestrator_payload: dict[str, Any] = {"messages": enhanced_messages}
        if model_override is not None:
            orchestrator_payload["model"] = model_override
        if chat_request.temperature is not None:
            orchestrator_payload["temperature"] = chat_request.temperature
        if chat_request.max_tokens is not None:
            orchestrator_payload["max_tokens"] = chat_request.max_tokens

        debug_enabled = http_request.headers.get("x-openclaw-debug", "") == "1"
        if debug_enabled:
            logger.info(
                "OpenClaw debug: incoming chat request",
                extra={
                    "event_type": "openclaw_debug",
                    "metadata": {
                        "path": str(http_request.url.path),
                        "model": chat_request.model,
                        "stream": bool(chat_request.stream),
                        "message_roles": [m.get("role") for m in chat_request.messages],
                        "content_types": [
                            type(m.get("content")).__name__ for m in chat_request.messages
                        ],
                    },
                },
            )

        response = ORCH_SESSION.post(
            orchestrator_url, json=orchestrator_payload, timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            result = response.json()

            # Compatibility: some OpenAI-compatible clients still look for legacy
            # `choices[].text` (completions-style) even when calling chat endpoints.
            # Provide it as a mirror of `choices[].message.content` when possible.
            try:
                choices = result.get("choices")
                if isinstance(choices, list):
                    for choice in choices:
                        if not isinstance(choice, dict):
                            continue
                        if "text" in choice and isinstance(choice.get("text"), str):
                            continue
                        msg = choice.get("message")
                        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                            choice["text"] = msg["content"]
            except Exception:
                # Never fail a chat completion due to a best-effort compatibility shim.
                pass

            # Some clients treat usage=0 as "no output". Provide a tiny best-effort estimate
            # when the orchestrator doesn't return token accounting.
            try:
                usage = result.get("usage")
                if not isinstance(usage, dict):
                    usage = {}
                    result["usage"] = usage

                def _est_tokens(s: str) -> int:
                    # Lightweight heuristic: ~4 chars/token. Clamp to >=1 when non-empty.
                    s = s.strip()
                    if not s:
                        return 0
                    return max(1, len(s) // 4)

                prompt_text = "\n".join(
                    [
                        f"{m.get('role','')}: {m.get('content','')}"
                        for m in enhanced_messages
                        if isinstance(m.get("content"), str)
                    ]
                )
                completion_text = ""
                choices = result.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    if isinstance(first, dict):
                        msg = first.get("message")
                        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                            completion_text = msg["content"]
                        elif isinstance(first.get("text"), str):
                            completion_text = first["text"]

                est_prompt = _est_tokens(prompt_text)
                est_completion = _est_tokens(completion_text)

                # If the backend didn't measure tokens (0s) but we do have text,
                # overwrite with an estimate so clients don't treat the reply as empty.
                if int(usage.get("prompt_tokens") or 0) == 0 and est_prompt > 0:
                    usage["prompt_tokens"] = est_prompt
                if int(usage.get("completion_tokens") or 0) == 0 and est_completion > 0:
                    usage["completion_tokens"] = est_completion

                total = int(usage.get("prompt_tokens") or 0) + int(
                    usage.get("completion_tokens") or 0
                )
                if int(usage.get("total_tokens") or 0) == 0 and total > 0:
                    usage["total_tokens"] = total
            except Exception:
                pass

            if debug_enabled:
                try:
                    choices = result.get("choices")
                    first_text = None
                    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                        first_text = choices[0].get("text")
                    logger.info(
                        "OpenClaw debug: outgoing chat response",
                        extra={
                            "event_type": "openclaw_debug",
                            "metadata": {
                                "has_choices": isinstance(result.get("choices"), list),
                                "first_choice_has_text": isinstance(first_text, str),
                                "usage": result.get("usage"),
                            },
                        },
                    )
                except Exception:
                    pass

            # Log the interaction
            logger.info(
                f"Request processed: domains={processed.domain_weights.model_dump()}, "
                f"units={len(processed.extracted_units)}, constraints={len(processed.constraints)}"
            )

            if chat_request.stream:
                # OpenAI-style SSE streaming. The Control UI expects this when stream=true.
                # We stream the already-produced content as a single delta chunk + stop chunk.
                def _sse_lines():
                    try:
                        resp_id = result.get("id") or f"chatcmpl-{int(datetime.utcnow().timestamp())}"
                        model = result.get("model") or (chat_request.model or "unknown")
                        created = result.get("created") or int(datetime.utcnow().timestamp())

                        content = ""
                        try:
                            choices = result.get("choices")
                            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                                msg = choices[0].get("message")
                                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                                    content = msg["content"]
                                elif isinstance(choices[0].get("text"), str):
                                    content = choices[0]["text"]
                        except Exception:
                            content = ""

                        chunk = {
                            "id": resp_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": content} if content else {},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                        done = {
                            "id": resp_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {"index": 0, "delta": {}, "finish_reason": "stop"}
                            ],
                        }
                        yield f"data: {json.dumps(done)}\n\n"
                        yield "data: [DONE]\n\n"
                    except Exception as e:
                        # If streaming fails, emit an error-ish termination rather than hanging.
                        err = {
                            "error": {
                                "message": f"streaming failed: {e}",
                                "type": "server_error",
                            }
                        }
                        yield f"data: {json.dumps(err)}\n\n"
                        yield "data: [DONE]\n\n"

                return StreamingResponse(
                    _sse_lines(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    },
                )

            return result
        else:
            logger.error(
                f"Orchestrator returned {response.status_code}: {response.text}"
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "orchestrator_error",
                    "message": "Orchestrator returned a non-200 response.",
                    "orchestrator_status": response.status_code,
                    "debug_hint": "Check wrkhrs-agent-platform logs and verify ORCHESTRATOR_URL + LLM_BACKEND configuration.",
                },
            )

    except requests.exceptions.RequestException as e:
        logger.error(f"Error contacting orchestrator: {e}")
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": "orchestrator_unreachable",
                "message": "Error contacting orchestrator.",
                "debug_hint": "Check wrkhrs-gateway logs, ORCHESTRATOR_URL, and that wrkhrs-agent-platform is healthy.",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat_completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_prompt(prompt: str) -> ProcessedPrompt:
    """Process prompt with non-generative conditioning"""
    # Extract domain weights
    domain_weights = extract_domain_weights(prompt)

    # Extract units and constraints
    units = extract_units(prompt)
    constraints = extract_constraints(prompt)

    # Get weighted evidence from RAG
    evidence = await get_weighted_evidence(prompt, domain_weights)

    return ProcessedPrompt(
        original_prompt=prompt,
        domain_weights=domain_weights,
        extracted_units=units,
        constraints=constraints,
        weighted_evidence=evidence,
    )


@api.get("/domains/analyze")
async def analyze_domains(text: str):
    """Endpoint to analyze domain weights for debugging"""
    weights = extract_domain_weights(text)
    units = extract_units(text)
    constraints = extract_constraints(text)

    return {
        "domain_weights": weights.model_dump(),
        "units": units,
        "constraints": constraints,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(api, host="0.0.0.0", port=8000)
