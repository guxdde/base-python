# AGENTS.md - AI Agent 开发指南

本文档为 AI Agent 在本代码库中工作提供指南。

## 项目概览

- **框架**: FastAPI (异步) + SQLAlchemy (异步 ORM) + Dramatiq + Periodiq + Redis
- **Python 版本**: 3.10+
- **配置**: 基于 YAML (`config.yaml`) + Pydantic 校验
- **数据库**: MySQL/PostgreSQL (多数据库支持)
- **测试**: pytest

## 构建 / 运行命令

### 开发服务器
```bash
# 启动 FastAPI 应用
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Dramatiq Workers
```bash
# 启动 Dramatiq worker (消费消息)
dramatiq app.tasks --workers 4

# 启动 Periodiq (定时任务调度器, 单独进程)
periodiq -v app

# 带代码热重载
dramatiq app.tasks --watch .
```

### 运行测试
```bash
# 运行所有测试
pytest

# 运行指定测试文件
pytest tests/test_dramatiq_integration.py

# 运行单个测试
pytest tests/test_dramatiq_integration.py::test_dramatiq_actor_basic -v

# 运行并生成覆盖率报告
pytest --cov=app tests/
```

### 数据库迁移 (Alembic)
```bash
# 生成迁移脚本
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head
```

## 代码风格指南

### 基本原则
- 所有 I/O 操作 (数据库、Redis、HTTP) 使用 **async/await**
- 所有函数参数和返回值使用 **类型提示**
- 保持函数小而专注 (单一职责)
- 使用 FastAPI 的 `Depends` 进行 **依赖注入**

### 命名规范
- **文件**: snake_case (如 `dramatiq_broker.py`, `market_base_service.py`)
- **类**: PascalCase (如 `DatabaseManager`, `MarketBaseService`)
- **函数/变量**: snake_case (如 `get_session`, `broker`)
- **常量**: UPPER_SNAKE_CASE (如 `DEFAULT_TIMEOUT`)
- **数据库表**: snake_case 加下划线

### 导入顺序
1. 标准库
2. 第三方包
3. 本地应用导入

```python
# 标准库
import logging
from typing import Optional, List
from contextlib import asynccontextmanager

# 第三方
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# 本地应用
from app.core.config import settings
from app.core.database import get_session
from app.models.tenant import Tenant
```

### 类型提示
始终使用类型提示。可空类型使用 `Optional`:

```python
# 正确
def get_user(user_id: int) -> Optional[User]:
    ...

async def process_data(data_id: int, options: dict | None = None) -> dict:
    ...
```

### 错误处理
- 使用 try/except 捕获具体异常类型
- 始终记录异常上下文
- 通过 API 返回有意义的错误响应

```python
# 正确
try:
    result = await some_async_operation()
except ValueError as e:
    logger.warning(f"Invalid input: {e}")
    raise
except Exception as e:
    logger.exception(f"Operation failed: {e}")
    return {"error": str(e)}
```

### 数据库模型
- 使用 SQLAlchemy 异步 ORM 的 `Base` 类
- 模型定义在 `app/models/`
- 使用 `Column` 明确定义类型和约束
- 复杂字段添加注释

```python
class Tenant(Base):
    __tablename__ = "tenant"

    id = Column(Integer, primary_key=True)
    company_name = Column(String(40), nullable=True, comment="公司名称")
    status = Column(Enum(TenantStatusEnum), default=TenantStatusEnum.active)
```

### Dramatiq 任务
使用 `@dramatiq.actor` 装饰器定义任务：

```python
import dramatiq

@dramatiq.actor(queue_name='default', time_limit=60000, max_retries=3)
def process_task(data: dict) -> dict:
    """处理任务并设置超时限制 (毫秒)"""
    return {"result": "success"}
```

调用任务：
```python
# 异步调用
result = process_task.send(data)

# 延迟调用 (毫秒)
result = process_task.send_with_options(args=(data,), delay=60000)
```

### Dramatiq 定时任务
使用 `periodic` 参数结合 Periodiq 的 `cron` 函数：

```python
import dramatiq
from periodiq import cron

# Cron 表达式: "分 时 日 月 周"
@dramatiq.actor(periodic=cron("*/10 * * * *"), queue_name="default")
def sync_data():
    """每10分钟执行"""
    pass

@dramatiq.actor(periodic=cron("0 9 * * *"), queue_name="default")
def daily_task():
    """每天9点执行"""
    pass

@dramatiq.actor(periodic=cron("0 */2 * * *"), queue_name="default")
def hourly_task():
    """每2小时执行"""
    pass
```

| Cron 表达式 | 说明 |
|-------------|------|
| `*/10 * * * *` | 每10分钟 |
| `0 * * * *` | 每小时整点 |
| `0 9 * * *` | 每天9点 |
| `0 */2 * * *` | 每2小时 |
| `0 0 * * 1` | 每周一零点 |

### API 端点
- 继承 `BaseHTTPEndpoint` 以保持响应格式一致
- 使用 `success_response()` 和 `error_response()` 辅助方法

```python
class MyEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        data = await fetch_data()
        return self.success_response({"items": data})
```

### 配置
- 所有配置通过 `config.yaml`
- Pydantic 模型定义在 `app/core/config.py`
- 通过 `settings` 单例访问

```python
from app.core.config import settings

db_url = settings.default_db.url
redis_url = settings.redis.url
rabbitmq_conf = settings.rabbitmq
```

### 日志
- 使用 Python 的 `logging` 模块
- 在模块级别获取 logger: `logger = logging.getLogger(__name__)`

## 项目结构

```
base-python/
├── main.py                    # 应用入口
├── config.yaml                # 配置文件
├── requirements.txt           # 依赖
├── app/
│   ├── factory.py            # FastAPI 工厂
│   ├── tasks/                # 定时任务定义
│   │   ├── __init__.py
│   │   └── scheduled_tasks.py # 定时任务示例
│   ├── core/                 # 核心组件
│   │   ├── dramatiq_broker.py # Dramatiq Broker 配置
│   │   ├── dramatiq_tasks.py  # 任务装饰器
│   │   ├── task_result.py     # 任务结果存储 (Redis)
│   │   ├── config.py         # 配置模型
│   │   ├── database.py       # 数据库管理
│   │   ├── redis.py          # Redis 客户端
│   │   ├── dead_letter.py    # 死信管理
│   │   └── base_endpoint.py  # 基础 HTTP 端点
│   ├── models/               # SQLAlchemy 模型
│   ├── api/                  # API 端点
│   │   ├── tasks/           # 任务管理 API
│   │   ├── dead_letter/     # 死信管理
│   │   └── health/          # 健康检查
│   └── services/             # 业务逻辑服务
└── tests/                   # 测试文件
```

## 常用模式

### 数据库会话
```python
async def my_endpoint(request):
    async with dbm.session("default") as session:
        result = await session.execute(select(Model))
        return result.scalars().all()
```

### Redis 操作
```python
from app.core.redis import redis_service

# 异步
value = await redis_service.get(key)

# 同步辅助
redis = get_redis_sync()
value = redis.get(key)
```

### 调用 Dramatiq 任务
```python
from app.core.dramatiq_broker import get_broker

broker = get_broker()
actors = broker.actors
actor = actors.get("task_name")

# 发送任务
message = actor.send(data)

# 延迟发送
message = actor.send_with_options(args=(data,), delay=60000)
```

## AI Agent 注意事项

- 代码库中部分位置使用中文注释，请保留
- 始终使用异步数据库会话 (不要用同步)
- 配置通过 `config.yaml` 管理环境差异
- config.yaml 中的敏感信息不应提交 (本地开发使用 `.env`)
- 新增端点请遵循 `app/api/` 中的现有模式
- Dramatiq 任务必须使用 JSON 可序列化的参数
- 时间限制以毫秒为单位 (如 `time_limit=60000` = 60秒)
