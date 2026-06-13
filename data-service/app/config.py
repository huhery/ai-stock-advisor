import os


MYSQL_HOST = os.getenv('MYSQL_HOST', '81.69.42.239')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'AiStock2026!')
MYSQL_DB = os.getenv('MYSQL_DB', 'ai_stock')

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://integrate.api.nvidia.com/v1')
LLM_MODEL = os.getenv('LLM_MODEL', 'meta/llama-3.1-70b-instruct')
