# FastAPI 异步框架 + Celery 集成

## 概述

本项目是一个基于 FastAPI 的异步框架，集成 Celery 进行任务队列处理，支持任务自动注册、Beat 定时任务代码配置、数据库死信管理等功能。

## 功能特性

- **任务自动注册** - 使用 `@celery_task` 装饰器自动注册任务
- **Beat 代码配置** - 使用装饰器配置定时任务，无需配置文件
- **数据库死信** - 任务失败自动记录到数据库，支持重试
- **RESTful API** - 任务管理和死信管理的 HTTP 接口

## 环境要求

- Python 3.9+
- MySQL 5.7+
- Redis 5.0+
- RabbitMQ (可选，作为 Celery broker)

## 安装配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 config.yaml

复制 `config.yaml` 示例文件并根据实际情况修改：

```yaml
default_db:
  database_type: mysql
  host: localhost
  db: your_database
  port: 3306
  user: root
  password: your_password
  pool_size: 20
  max_overflow: 40

redis:
  host: localhost
  port: 6379
  password: ""

rabbitmq:
  host: localhost
  port: 5672
  username: guest
  password: guest
  virtual_host: "/"

celery:
  result_backend: redis://localhost:6379/1
  task_default_queue: default
  task_acks_late: true
  worker_prefetch_multiplier: 1
  default_soft_time_limit: 30
  default_time_limit: 60
  rabbitmq:
    enabled: true
    exchange: dlx.exchange
    queue: dlq.default
    routing_key: dlq
```

## 任务定义

### 基本任务

```python
from app.core.celery import celery_task

@celery_task(queue='default', soft_time_limit=30)
def add_task(a, b):
    """计算两个数的和"""
    return a + b
```

### 任务参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `queue` | str | 任务队列名称 |
| `soft_time_limit` | int | 软超时时间（秒） |
| `time_limit` | int | 硬超时时间（秒） |
| `name` | str | 任务名称（默认使用函数名） |
| `description` | str | 任务描述 |
| `tags` | list | 任务标签 |

## 定时任务配置

### 使用 cron 表达式

```python
from app.core.beat import beat_scheduler

# 每天凌晨2点执行
@beat_scheduler.every("0 2 * * *")
def daily_report():
    pass

# 每5分钟执行
@beat_scheduler.every("*/5 * * * *")
def periodic_cleanup():
    pass
```

### 使用 interval

```python
# 每30分钟执行
@beat_scheduler.interval(minutes=30)
def half_hourly_task():
    pass

# 每2小时执行
@beat_scheduler.interval(hours=2)
def hourly_task():
    pass

# 每60秒执行
@beat_scheduler.interval(seconds=60)
def frequent_task():
    pass
```

### 使用 crontab 细粒度控制

```python
# 每周一至周五上午9点执行
@beat_scheduler.crontab(hour="9", minute="0", day_of_week="1-5")
def weekday_morning_task():
    pass

# 每月1日凌晨执行
@beat_scheduler.crontab(hour="0", minute="0", day_of_month="1")
def monthly_task():
    pass
```

### 动态添加定时任务

```python
from app.core.beat import beat_scheduler

beat_scheduler.add(
    task_name="custom_task",
    task="app.tasks.my_module.custom_task",
    schedule=60,  # 每60秒
    options={"queue": "default"}
)
```

## 启动服务

### 1. 启动 FastAPI 应用

```bash
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8080
```

### 2. 启动 Celery Worker

```bash
celery -A app.core.celery._celery_app_instance worker --loglevel=info
```

### 3. 启动 Celery Beat (定时任务)

```bash
celery -A app.core.celery._celery_app_instance beat --loglevel=info
```

## API 接口

### 任务管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/tasks/` | GET | 列出所有任务 |
| `/api/tasks/register` | GET | 获取已注册任务列表 |
| `/api/tasks/run` | POST | 执行任务 |
| `/api/tasks/{task_name}` | GET | 获取任务详情 |
| `/api/tasks/status/{task_id}` | GET | 查询任务状态 |
| `/api/tasks/cancel/{task_id}` | POST | 取消任务 |

#### 执行任务示例

```bash
curl -X POST http://localhost:8080/api/tasks/run \
  -H "Content-Type: application/json" \
  -d '{"task_name": "add_task", "args": [1, 2]}'
```

#### 查询任务状态

```bash
curl http://localhost:8080/api/tasks/status/{task_id}
```

### 死信管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/dead-letters/` | GET | 列出死信列表 |
| `/api/dead-letters/stats` | GET | 死信统计 |
| `/api/dead-letters/{id}` | GET | 死信详情 |
| `/api/dead-letters/{id}/retry` | POST | 重试任务 |
| `/api/dead-letters/{id}/resolve` | POST | 标记已解决 |
| `/api/dead-letters/{id}` | DELETE | 删除记录 |

#### 重试死信示例

```bash
curl -X POST http://localhost:8080/api/dead-letters/1/retry \
  -H "Content-Type: application/json" \
  -d '{"queue": "default"}'
```

## 代码示例

### 完整示例

```python
# app/tasks/example.py
from app.core.celery import celery_task
from app.core.beat import beat_scheduler

# 定义任务
@celery_task(queue='default', soft_time_limit=60)
def process_data(data_id: int):
    """处理数据"""
    # 业务逻辑
    result = f"Processed data {data_id}"
    return result

# 定义定时任务
@beat_scheduler.every("*/10 * * * *")
def cleanup_expired_sessions():
    """清理过期会话"""
    # 清理逻辑
    pass
```

### 在代码中调用任务

```python
from app.factory import get_celery_app

# 获取 Celery 应用
celery_app = get_celery_app()

# 异步调用任务
result = celery_app.send_task(
    'add_task',
    args=[1, 2],
    kwargs={},
    queue='default'
)

# 获取任务 ID
task_id = result.id
```

## 项目结构

```
base-python/
├── main.py                      # 应用入口
├── config.yaml                  # 配置文件
├── requirements.txt             # 依赖
├── app/
│   ├── factory.py              # FastAPI 工厂
│   ├── core/
│   │   ├── celery.py           # Celery 核心
│   │   ├── task_registry.py    # 任务注册表
│   │   ├── beat.py             # Beat 调度器
│   │   ├── dead_letter.py      # 死信管理器
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库
│   │   └── redis.py            # Redis
│   ├── models/
│   │   └── dead_letter.py      # 死信模型
│   └── api/
│       ├── tasks/
│       │   └── tasks.py        # 任务 API
│       └── dead_letter/
│           └── dead_letter.py  # 死信 API
└── tests/
```

## 常见问题

### 1. Celery Worker 无法启动

检查 `config.yaml` 中的 RabbitMQ/Redis 配置是否正确。

### 2. 任务未自动注册

确保任务模块被导入，`@celery_task` 装饰器在模块加载时执行注册。

### 3. 定时任务不执行

确保启动了 Celery Beat：
```bash
celery -A app.core.celery._celery_app_instance beat
```

### 4. 死信未保存到数据库

检查数据库连接配置，确保 `dead_letter_records` 表已创建。
