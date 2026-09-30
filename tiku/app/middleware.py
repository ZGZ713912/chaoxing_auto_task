"""
限流和并发控制中间件
"""

import time
import asyncio
import threading
import logging
from collections import defaultdict
from typing import Dict, List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import (
    RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW,
    REQUEST_TIMEOUT, MAX_CONCURRENT_REQUESTS
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """请求限流器 - 基于滑动窗口算法"""

    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str) -> bool:
        current_time = time.time()
        with self._lock:
            self._requests[client_id] = [
                t for t in self._requests[client_id]
                if current_time - t < self.window_seconds
            ]
            if len(self._requests[client_id]) >= self.max_requests:
                return False
            self._requests[client_id].append(current_time)
            return True

    def get_remaining(self, client_id: str) -> int:
        current_time = time.time()
        with self._lock:
            self._requests[client_id] = [
                t for t in self._requests[client_id]
                if current_time - t < self.window_seconds
            ]
            return max(0, self.max_requests - len(self._requests[client_id]))


rate_limiter = RateLimiter()


class ConcurrencyCounter:
    """并发请求计数器"""

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_REQUESTS):
        self.max_concurrent = max_concurrent
        self._count = 0
        self._lock = threading.Lock()

    def increment(self) -> bool:
        with self._lock:
            if self._count >= self.max_concurrent:
                return False
            self._count += 1
            return True

    def decrement(self):
        with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def current(self) -> int:
        with self._lock:
            return self._count


concurrency_counter = ConcurrencyCounter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流和超时中间件"""

    async def dispatch(self, request: Request, call_next):
        client_id = request.client.host if request.client else "unknown"

        if not concurrency_counter.increment():
            return JSONResponse(
                status_code=503,
                content={"code": 0, "msg": "服务器繁忙，请稍后重试", "data": None}
            )

        try:
            if not rate_limiter.is_allowed(client_id):
                remaining = rate_limiter.get_remaining(client_id)
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 0,
                        "msg": f"请求过于频繁，请{RATE_LIMIT_WINDOW}秒后重试",
                        "data": {"remaining": remaining}
                    },
                    headers={"Retry-After": str(RATE_LIMIT_WINDOW)}
                )

            try:
                response = await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT)
                return response
            except asyncio.TimeoutError:
                logger.warning(f"请求超时: {request.url.path} (client: {client_id})")
                return JSONResponse(
                    status_code=504,
                    content={"code": 0, "msg": "请求超时，请稍后重试", "data": None}
                )
        finally:
            concurrency_counter.decrement()
