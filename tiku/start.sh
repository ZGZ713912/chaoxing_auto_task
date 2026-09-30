#!/bin/bash

# 司索工题库服务器启动脚本 (高性能并发版本)
# 可用端口: 8001, 8002, 8003, 8004
# 支持100+并发请求

# 默认端口
PORT=${1:-8001}

# 是否启用高性能模式（多工作进程）
HIGH_PERFORMANCE=${2:-false}

# 检查端口范围
if [[ $PORT -lt 8001 || $PORT -gt 8004 ]]; then
    echo "错误: 端口必须在 8001-8004 之间"
    echo "用法: ./start.sh [端口] [高性能模式]"
    echo "示例: ./start.sh 8001        # 普通模式"
    echo "示例: ./start.sh 8001 true   # 高性能模式(100并发)"
    exit 1
fi

echo "=========================================="
echo "    司索工题库服务器 (高性能并发版)"
echo "    支持 100+ 并发请求"
echo "=========================================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -q -r requirements.txt

echo ""
echo "启动服务器..."
echo "- 管理界面: http://localhost:$PORT"
echo "- API接口:  http://localhost:$PORT/api/search"
echo "- 端口:     $PORT"

# 高性能模式配置
if [ "$HIGH_PERFORMANCE" = "true" ]; then
    # 获取CPU核心数
    CPU_CORES=$(nproc)
    # 计算工作进程数：CPU核心数 * 2 + 1，但不超过4个
    WORKERS=$((CPU_CORES * 2 + 1))
    if [ $WORKERS -gt 4 ]; then
        WORKERS=4
    fi
    
    echo "- 模式:     高性能模式"
    echo "- 工作进程: $WORKERS (基于CPU核心数: $CPU_CORES)"
    echo "- 并发能力: 100+ 并发请求"
    echo "- 限流配置: 200请求/分钟/IP"
    echo ""
    echo "提示: 使用 ./start.sh $PORT true 启动高性能模式"
    echo "=========================================="
    echo ""
    
    # 使用uvloop和httptools优化性能
    export PORT=$PORT
    export WORKERS=$WORKERS
    
    # 启动高性能服务器
    exec python3 -c "
import uvicorn
import os
port = int(os.environ.get('PORT', 8001))
workers = int(os.environ.get('WORKERS', 4))
print(f'启动 {workers} 个工作进程...')
uvicorn.run(
    'main:app',
    host='0.0.0.0',
    port=port,
    workers=workers,
    loop='uvloop',
    http='httptools',
    access_log=False,
    limit_concurrency=150,
    timeout_keep_alive=30
)
"
else
    echo "- 模式:     普通模式"
    echo "- 并发能力: 100+ 并发请求"
    echo "- 限流配置: 200请求/分钟/IP"
    echo ""
    echo "按 Ctrl+C 停止服务器"
    echo "=========================================="
    echo ""
    
    # 启动普通服务器
    export PORT=$PORT
    python3 main.py
fi
