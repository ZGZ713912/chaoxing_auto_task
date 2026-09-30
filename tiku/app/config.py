"""
配置常量和环境变量
"""

import os

# ============ 数据库配置 ============
DATABASE_FILE = "questions.db"
JSON_FILE = "tiku.json"

# ============ 服务器配置 ============
API_KEY = os.environ.get("API_KEY", "your_api_key")
DEFAULT_PORT = 8001

# ============ 请求限制 ============
MAX_QUESTION_LENGTH = 10000
MAX_OPTIONS_COUNT = 20
MAX_SEARCH_LENGTH = 500
MAX_LIMIT = 1000
MAX_OFFSET = 100000

# ============ 限流配置 ============
RATE_LIMIT_REQUESTS = 200
RATE_LIMIT_WINDOW = 60
REQUEST_TIMEOUT = 30
MAX_CONCURRENT_REQUESTS = 150
