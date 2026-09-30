"""
司索工题库服务器 - FastAPI 应用工厂
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import (
    DATABASE_FILE, JSON_FILE, DEFAULT_PORT,
    RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW,
    REQUEST_TIMEOUT, MAX_CONCURRENT_REQUESTS
)
from .database import AsyncDatabase
from .middleware import RateLimitMiddleware, rate_limiter, concurrency_counter
from .routes import search_router, questions_router, pending_router, admin_router

logger = logging.getLogger(__name__)

# 全局数据库实例
db: AsyncDatabase = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global db
    db = AsyncDatabase(DATABASE_FILE)
    await db.init_db()

    count = await db.get_count()
    if count == 0:
        await db.import_from_json(JSON_FILE)

    # 将 db 注入到 app.state 以便路由访问
    app.state.db = db

    print(f"题库服务器已启动，共 {count} 道题目")
    print(f"并发限制: {MAX_CONCURRENT_REQUESTS}")
    print(f"限流配置: {RATE_LIMIT_REQUESTS} 请求/{RATE_LIMIT_WINDOW}秒")
    print(f"请求超时: {REQUEST_TIMEOUT}秒")

    yield

    print("正在关闭服务器...")
    try:
        if db:
            async with db._pool_lock:
                for conn in db._connection_pool:
                    try:
                        await conn.close()
                    except Exception as e:
                        logger.error(f"关闭数据库连接失败: {e}")
                db._connection_pool.clear()
        print("资源清理完成")
    except Exception as e:
        logger.error(f"资源清理失败: {e}")
    print("题库服务器已关闭")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误"""
    logger.warning(f"请求验证错误: {exc}")
    return JSONResponse(
        status_code=422,
        content={"code": 0, "msg": "请求参数错误", "detail": str(exc)}
    )


async def global_exception_handler(request: Request, exc: Exception):
    """处理全局未捕获异常"""
    logger.error(f"未捕获的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 0, "msg": "服务器内部错误"}
    )


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="司索工题库服务器",
        description="支持题目查询API和Web管理界面 - 高性能并发版本",
        version="2.2.0",
        lifespan=lifespan
    )

    # 注册异常处理器
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 限流中间件
    app.add_middleware(RateLimitMiddleware)

    # 静态文件
    os.makedirs("static", exist_ok=True)
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

    # 注册 API 路由
    app.include_router(search_router)
    app.include_router(questions_router)
    app.include_router(pending_router)
    app.include_router(admin_router)

    # SPA fallback - 所有非 API、非 assets 的 GET 请求返回 index.html
    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def spa_fallback(full_path: str):
        # 检查是否是静态文件
        static_file = os.path.join("static", full_path)
        if os.path.isfile(static_file):
            from fastapi.responses import FileResponse
            return FileResponse(static_file)
        # 返回 SPA index.html
        index_path = os.path.join("static", "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>请先构建前端: cd frontend && npm run build</h1>")

    return app
