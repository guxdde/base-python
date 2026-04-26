# AGENTS.md - AI Agent 开发指南

本文档为 AI Agent 在本代码库中工作提供指南。

## 项目概览

- **框架**: FastAPI (异步) + SQLAlchemy (异步 ORM) + TaskIQ + Redis
- **Python 版本**: 3.9+
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

### TaskIQ Workers
```bash
# 启动 TaskIQ worker
taskiq worker -m app.core.taskiq:broker

# 或指定队列
taskiq worker -m app.core.taskiq:broker -q default,high_priority,low_priority
```

### 运行测试
```bash
# 运行所有测试
pytest

# 运行指定测试文件
pytest tests/test_taskiq_integration.py

# 运行单个测试
pytest tests/test_taskiq_integration.py::test_taskiq_task_basic -v

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
- **文件**: snake_case (如 `task_registry.py`, `market_base_service.py`)
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

### TaskIQ 任务
- 使用 `app.core.taskiq.broker` 的 `.task()` 方法
- 通过参数定义队列、优先级、超时时间

```python
from app.core.taskiq import broker, QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW

@broker.task(queue_name=QUEUE_HIGH, priority=5, timeout=60)
async def process_task(data: dict) -> dict:
    """处理任务并设置超时限制"""
    return {"result": "success"}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `queue_name` | str | 队列名称 (high_priority/default/low_priority) |
| `priority` | int | 消息优先级 (1-10) |
| `timeout` | int | 硬超时时间（秒） |
| `soft_timeout` | int | 软超时时间（秒） |

### 发送任务

```python
# 使用任务定义的默认队列和优先级
task = await task_func.kiq(arg1, arg2)

# 运行时覆盖队列和优先级
kicker = task_func.kicker().with_labels(queue_name="high_priority", priority=8)
task = await kicker.kiq(arg1, arg2)
```

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
│   │   └── scheduled_tasks.py # 任务示例
│   ├── core/                 # 核心组件
│   │   ├── taskiq.py         # TaskIQ 配置
│   │   ├── config.py         # 配置模型
│   │   ├── database.py       # 数据库管理
│   │   ├── redis.py          # Redis 客户端
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

### 调用 TaskIQ 任务
```python
from app.core.taskiq import broker

# 通过 kicker 发送任务
kicker = task_func.kicker().with_labels(queue_name="default")
task = await kicker.kiq(arg1, arg2)

# 或直接调用
task = await task_func.kiq(arg1, arg2)
```

## AI Agent 注意事项

- 代码库中部分位置使用中文注释，请保留
- 始终使用异步数据库会话 (不要用同步)
- 配置通过 `config.yaml` 管理环境差异
- config.yaml 中的敏感信息不应提交 (本地开发使用 `.env`)
- 新增端点请遵循 `app/api/` 中的现有模式