"""
司索工题库服务器 - 入口文件
"""

import os
import logging
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from app import create_app

app = create_app()

if __name__ == "__main__":
    from app.config import DEFAULT_PORT

    port = int(os.environ.get("PORT", DEFAULT_PORT))
    workers = int(os.environ.get("WORKERS", 1))

    print(f"启动题库服务器...")
    print(f"API地址: http://localhost:{port}/api/search")
    print(f"管理界面: http://localhost:{port}/")
    print(f"工作进程: {workers}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        loop="auto",
        http="auto",
        access_log=False
    )
