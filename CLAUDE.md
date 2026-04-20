# CLAUDE.md - Project Configuration Guide

This file provides guidance for Claude Code when working with this Python/FastAPI project.

## Project Structure

```
app/
├── api/              # API routes
│   ├── v1/          # API v1 routes
│   └── tasks/       # Task-related routes
├── core/            # Core utilities
│   ├── base_endpoint.py  # Base HTTP endpoint
│   ├── celery.py         # Celery task configuration
│   ├── database.py       # Database connection/session
│   ├── logger.py         # Logging configuration
│   ├── redis.py          # Redis client wrapper
│   └── config.py         # Settings/Configuration
├── models/          # Data models (Pydantic/SQLAlchemy)
├── schemas/         # Request/Response schemas
├── tasks/           # Celery task definitions
└── main.py          # FastAPI application entry point
```

## Key Components

### 1. API Endpoints
- Base class: `BaseHTTPEndpoint` from `app.core.base_endpoint`
- Response handling: Uses `success_response()` and `error_response()` methods
- Router: `APIRouter` from FastAPI

### 2. Database
- Connection: `core.database` module
- Session management: `get_session()`, `SessionLocal`, or `create_session()`
- Async support: `await get_session()` for async operations

### 3. Redis
- Client: `core.redis` module with `RedisService` class
- Global instance: `redis_service`
- Functions: `get_redis()`, `get_redis_sync()`, `init_redis_client()` context manager
- Features: Auto-reconnect, health checks, retry logic

### 4. Celery Tasks
- Configuration: `core.celery` module
- Task decorator: `@celery_task` for auto-registration
- Broker: RabbitMQ (AMQP) with fallback to Redis
- Features: Dead letter queues, beat scheduler, signal handlers for resource injection

### 5. Configuration
- Settings: `core.config.settings` (likely Pydantic Settings)
- Environment variables: Loaded via `python-dotenv` or similar

## Common Patterns

### Creating API Endpoints
```python
from app.core.base_endpoint import BaseHTTPEndpoint

class MyEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        return self.success_response({"data": "value"})
```

### Creating Celery Tasks
```python
from app.core import celery

@celery_task(queue='high', soft_time_limit=300, time_limit=600)
def my_task(arg1, arg2):
    # Task implementation
    pass
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
from app.core import database

async def use_db():
    session = await database.get_session()
    # Use session for queries
    await session.close()
```

## Important Notes

1. **Redis Connection**: Uses lazy initialization with health checks and automatic reconnection
2. **Celery Broker**: Prefers RabbitMQ, falls back to Redis if unavailable
3. **Task Signals**: Automatically injects DB session and Redis client into tasks
4. **Dead Letter Queues**: Tasks can be configured with DLX for retry management
5. **Beat Scheduler**: Supports both code-defined schedules and settings-based schedules

## File Locations

- Main app: `app/main.py`
- Config: `app/core/config.py`
- Database: `app/core/database.py`
- Redis: `app/core/redis.py`
- Celery: `app/core/celery.py`
- Tasks: `app/tasks/` and `app/api/tasks/`
- Beat scheduler: `app/beat.py`
- Dead letter manager: `app/dead_letter.py`

## Testing Tips

1. Check Redis connectivity: `await redis_service.ping()`
2. Verify Celery app: `get_celery_app()`
3. Test database session: `await database.get_session()`
4. Check settings: `settings` object attributes
