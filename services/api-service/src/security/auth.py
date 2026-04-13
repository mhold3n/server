"""Authentication and authorization middleware."""

import time
from collections.abc import Callable
from typing import Any

import structlog
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer

logger = structlog.get_logger()


class APIKeyAuth:
    """API key authentication."""

    def __init__(self, api_keys: dict[str, dict[str, Any]]):
        """Initialize API key auth.

        Args:
            api_keys: Dictionary of API keys and their permissions
        """
        self.api_keys = api_keys
        self.security = HTTPBearer()

    async def authenticate(self, request: Request) -> dict[str, Any]:
        """Authenticate request using API key.

        Args:
            request: FastAPI request

        Returns:
            Authentication result
        """
        try:
            # Extract API key from header
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required"
                )

            # Validate API key
            if api_key not in self.api_keys:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
                )

            # Get key info
            key_info = self.api_keys[api_key]

            # Check if key is active
            if not key_info.get("active", True):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key deactivated",
                )

            # Check expiration
            if "expires_at" in key_info:
                if time.time() > key_info["expires_at"]:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="API key expired",
                    )

            # Check rate limits
            await self._check_rate_limit(api_key, key_info)

            logger.info("API key authenticated", api_key=api_key[:8] + "...")

            return {
                "api_key": api_key,
                "permissions": key_info.get("permissions", []),
                "rate_limit": key_info.get("rate_limit", {}),
                "user_id": key_info.get("user_id"),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Authentication failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication error",
            ) from e

    async def _check_rate_limit(self, api_key: str, key_info: dict[str, Any]) -> None:
        """Check rate limits for API key.

        Args:
            api_key: API key
            key_info: Key information
        """
        rate_limit = key_info.get("rate_limit", {})
        if not rate_limit:
            return

        # This would integrate with Redis for rate limiting
        # For now, just log the check
        logger.info(
            "Rate limit check", api_key=api_key[:8] + "...", rate_limit=rate_limit
        )


class MCPAllowlist:
    """MCP server allowlist management."""

    def __init__(self, allowed_servers: set[str]):
        """Initialize MCP allowlist.

        Args:
            allowed_servers: Set of allowed MCP server names
        """
        self.allowed_servers = allowed_servers

    def is_allowed(self, server_name: str) -> bool:
        """Check if MCP server is allowed.

        Args:
            server_name: MCP server name

        Returns:
            True if allowed
        """
        return server_name in self.allowed_servers

    def add_server(self, server_name: str) -> None:
        """Add server to allowlist.

        Args:
            server_name: Server name to add
        """
        self.allowed_servers.add(server_name)
        logger.info("MCP server added to allowlist", server_name=server_name)

    def remove_server(self, server_name: str) -> None:
        """Remove server from allowlist.

        Args:
            server_name: Server name to remove
        """
        self.allowed_servers.discard(server_name)
        logger.info("MCP server removed from allowlist", server_name=server_name)


class CircuitBreaker:
    """Circuit breaker for service protection."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[BaseException] = Exception,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except BaseException as e:
            if not isinstance(e, self.expected_exception):
                raise
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if should attempt reset."""
        if self.last_failure_time is None:
            return True

        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning("Circuit breaker opened", failure_count=self.failure_count)


class RateLimiter:
    """Rate limiting for API endpoints."""

    def __init__(self, redis_client: Any | None = None) -> None:
        """Initialize rate limiter.

        Args:
            redis_client: Redis client for rate limiting
        """
        self.redis_client = redis_client

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> bool:
        """Check rate limit.

        Args:
            key: Rate limit key
            limit: Request limit
            window: Time window in seconds

        Returns:
            True if within limits
        """
        if not self.redis_client:
            # No rate limiting if no Redis
            return True

        try:
            current_time = int(time.time())
            window_start = current_time - window

            # Use sliding window counter
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, window)

            results = await pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                logger.warning(
                    "Rate limit exceeded", key=key, count=current_count, limit=limit
                )
                return False

            return True

        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            # Allow request if rate limiting fails
            return True


class SecurityMiddleware:
    """Security middleware for API protection."""

    def __init__(
        self,
        api_key_auth: APIKeyAuth,
        mcp_allowlist: MCPAllowlist,
        rate_limiter: RateLimiter,
    ):
        """Initialize security middleware.

        Args:
            api_key_auth: API key authentication
            mcp_allowlist: MCP allowlist
            rate_limiter: Rate limiter
        """
        self.api_key_auth = api_key_auth
        self.mcp_allowlist = mcp_allowlist
        self.rate_limiter = rate_limiter

    async def authenticate_request(self, request: Request) -> dict[str, Any]:
        """Authenticate request.

        Args:
            request: FastAPI request

        Returns:
            Authentication result
        """
        # Authenticate API key
        auth_result = await self.api_key_auth.authenticate(request)

        # Check rate limits
        api_key = auth_result["api_key"]
        rate_limit = auth_result.get("rate_limit", {})

        if rate_limit:
            limit = rate_limit.get("requests", 1000)
            window = rate_limit.get("window", 3600)

            allowed = await self.rate_limiter.check_rate_limit(
                f"rate_limit:{api_key}",
                limit,
                window,
            )

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                )

        return auth_result

    def check_mcp_permission(self, server_name: str) -> bool:
        """Check MCP server permission.

        Args:
            server_name: MCP server name

        Returns:
            True if allowed
        """
        return self.mcp_allowlist.is_allowed(server_name)

    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get circuit breaker for service.

        Args:
            service_name: Service name

        Returns:
            Circuit breaker instance
        """
        return CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
        )
