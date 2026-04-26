# CLAUDE.md - Project Configuration Guide

This file provides guidance for Claude Code when working with this Python/FastAPI project.

## Project Structure

```
app/
├── api/              # API routes
│   └── tasks/       # Task-related routes
├── core/            # Core utilities
│   ├── base_endpoint.py  # Base HTTP endpoint
│   ├── taskiq.py        # TaskIQ broker configuration
│   ├── database.py     # Database connection/session
│   ├── logger.py      # Logging configuration
│   ├── redis.py      # Redis client wrapper
│   └── config.py     # Settings/Configuration
├── models/          # Data models (SQLAlchemy)
├── tasks/           # Task definitions
└── factory.py      # FastAPI application factory
```

## Key Components

### 1. API Endpoints
- Base class: `BaseHTTPEndpoint` from `app.core.base_endpoint`
- Response handling: Uses `success_response()` and `error_response()` methods
- Router: `APIRouter` from FastAPI

### 2. Database
- Connection: `core.database` module
- Session management: `get_session()`, or use `DatabaseManager`
- Async support: `await get_session()` for async operations

### 3. Redis
- Client: `core.redis` module with `RedisService` class
- Global instance: `redis_service`
- Features: Auto-reconnect, health checks, retry logic

### 4. TaskIQ Tasks (Replaced Celery)
- Broker: `app.core.taskiq.broker` (AioPikaBroker with RabbitMQ)
- Task decorator: `@broker.task()` for task registration
- Result backend: Redis
- Features: Multi-queue priority, task scheduling, dependency injection

### 5. Configuration
- Settings: `core.config.settings` (Pydantic Settings)
- Environment variables: Loaded via `config.yaml`

## TaskIQ Configuration

### Task Queues
Three priority levels: `high_priority`, `default`, `low_priority`

```python
from app.core.taskiq import broker, QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW

@broker.task(queue_name=QUEUE_HIGH, priority=5, timeout=60)
async def sync_market_data():
    return {"status": "success"}
```

### Task Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `queue_name` | str | Queue name (high_priority/default/low_priority) |
| `priority` | int | Message priority (1-10, higher = more priority) |
| `timeout` | int | Hard timeout in seconds |
| `soft_timeout` | int | Soft timeout in seconds |

### Sending Tasks

```python
# Using default labels from task definition
task = await task_func.kiq(arg1, arg2)

# Override labels at runtime
kicker = task_func.kicker().with_labels(queue_name="high_priority", priority=8)
task = await kicker.kiq(arg1, arg2)
```

## Common Patterns

### Creating API Endpoints
```python
from app.core.base_endpoint import BaseHTTPEndpoint

class MyEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        return self.success_response({"data": "value"})
```

### Creating TaskIQ Tasks
```python
from app.core.taskiq import broker, QUEUE_HIGH

@broker.task(queue_name=QUEUE_HIGH, priority=5, timeout=60)
async def my_task(data: dict):
    return {"result": data}
```

### Using Redis
```python
from app.core import redis

async def use_redis():
    client = await redis.get_redis()
    await client.set("key", "value", expire=3600)
    value = await client.get("key")
```

### Using Database
```python
from app.core.database import DatabaseManager, db

async def use_db():
    async with dbm.session("default") as session:
        result = await session.execute(select(Model))
        await session.commit()
```

## Important Notes

1. **Redis Connection**: Uses lazy initialization with health checks
2. **TaskIQ Broker**: Uses RabbitMQ (aio-pika) with taskiq-aio-pika
3. **is_worker_process**: Used to distinguish API vs Worker process
4. **Multi-queue Priority**: Uses DIRECT exchange with routing keys

## File Locations

- Main app: `main.py`
- Config: `app/core/config.py`
- Database: `app/core/database.py`
- Redis: `app/core/redis.py`
- TaskIQ: `app/core/taskiq.py`
- Tasks: `app/tasks/`
- API: `app/api/tasks/`

## Testing Tips

1. Check Redis connectivity: `await redis_service.ping()`
2. Verify TaskIQ broker: `broker.is_worker_process`
3. Test database session: `await database.get_session()`
4. Check settings: `settings` object attributes