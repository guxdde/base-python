# FastAPI 异步框架 + TaskIQ

## 概述

本项目是一个基于 FastAPI 的异步框架，集成 TaskIQ 进行任务队列处理，支持任务自动注册、定时任务调度、数据库死信管理等功能。

## 功能特性

- **任务自动注册** - 使用 `@broker.task()` 装饰器自动注册任务
- **多队列优先级** - high_priority / default / low_priority 三级队列
- **定时任务** - 使用 TaskIQ Scheduler 配置定时任务
- **数据库死信** - 任务失败自动记录到数据库，支持重试
- **RESTful API** - 任务管理和死信管理的 HTTP 接口

## 环境要求

- Python 3.9+
- MySQL 5.7+
- Redis 5.0+
- RabbitMQ (TaskIQ Broker)

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

taskiq:
  result_backend_url: redis://localhost:6379/1
  broker_url: amqp://guest:guest@localhost:5672/
```

## 任务定义

### 基本任务

```python
from app.core.taskiq import broker, QUEUE_DEFAULT

@broker.task(queue_name=QUEUE_DEFAULT, priority=5, timeout=60)
async def add_task(a: int, b: int):
    """计算两个数的和"""
    return a + b
```

### 队列优先级

| 队列 | 常量 | 说明 |
|------|------|------|
| 高优先级 | `QUEUE_HIGH` | 紧急任务 |
| 默认 | `QUEUE_DEFAULT` | 普通任务 |
| 低优先级 | `QUEUE_LOW` | 后台任务 |

```python
from app.core.taskiq import broker, QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW

# 高优先级任务
@broker.task(queue_name=QUEUE_HIGH, priority=8, timeout=30)
async def sync_market_data():
    return {"status": "success"}

# 低优先级任务
@broker.task(queue_name=QUEUE_LOW, priority=2, timeout=600)
async def generate_report():
    return {"status": "success"}
```

### 任务参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `queue_name` | str | 任务队列名称 |
| `priority` | int | 消息优先级 (1-10) |
| `timeout` | int | 硬超时时间（秒） |
| `soft_timeout` | int | 软超时时间（秒） |

## 定时任务配置

定时任务定义在 `app/tasks/scheduled_tasks.py`：

```python
from app.core.taskiq import scheduler, broker, QUEUE_HIGH

@broker.task(queue_name=QUEUE_HIGH, priority=5, timeout=60)
async def sync_data():
    pass

# 使用 scheduler.schedule() 添加定时任务
```

## 启动服务

### 1. 启动 FastAPI 应用

```bash
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### 2. 启动 TaskIQ Worker

```bash
taskiq worker -m app.core.taskiq:broker

# 或指定队列
taskiq worker -m app.core.taskiq:broker -q default,high_priority,low_priority
```

### 3. 启动定时任务调度器（可选）

```bash
taskiq scheduler -m app.core.taskiq:scheduler
```

## API 接口

### 任务管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/tasks/` | GET | 列出所有任务 |
| `/api/tasks/register` | GET | 获取已注册任务列表 |
| `/api/tasks/run` | POST | 执行任务 |
| `/api/tasks/batch` | POST | 批量执行任务 |
| `/api/tasks/{task_name}` | GET | 获取任务详情 |
| `/api/tasks/status/{task_id}` | GET | 查询任务状态 |
| `/api/tasks/cancel/{task_id}` | POST | 取消任务 |

#### 执行任务示例

```bash
curl -X POST http://localhost:8080/api/tasks/run \
  -H "Content-Type: application/json" \
  -d '{"task_name": "add_task", "args": [1, 2], "kwargs": {}}'
```

#### 动态指定队列和优先级

```bash
curl -X POST http://localhost:8080/api/tasks/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "add_task",
    "args": [1, 2],
    "queue": "high_priority",
    "priority": 8
  }'
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
from app.core.taskiq import broker, QUEUE_HIGH, QUEUE_DEFAULT

# 定义任务
@broker.task(queue_name=QUEUE_DEFAULT, priority=5, timeout=60)
async def process_data(data_id: int):
    """处理数据"""
    result = f"Processed data {data_id}"
    return result
```

### 在代码中调用任务

```python
# 使用默认队列和优先级
task = await process_data.kiq(123)

# 动态覆盖队列和优先级
kicker = process_data.kicker().with_labels(
    queue_name=QUEUE_HIGH,
    priority=8
)
task = await kicker.kiq(123)
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
│   │   ├── taskiq.py           # TaskIQ broker 配置
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库
│   │   └── redis.py            # Redis
│   ├── tasks/
│   │   └── scheduled_tasks.py  # 任务定义
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

### 1. TaskIQ Worker 无法启动

检查 `config.yaml` 中的 RabbitMQ 配置是否正确。

### 2. 任务未自动注册

确保任务模块被导入，`@broker.task()` 装饰器在模块加载时执行注册。

### 3. 消息发送失败 "Routing key '' is not valid"

确保任务定义时设置了 `queue_name` label：
```python
@broker.task(queue_name=QUEUE_DEFAULT, ...)
```

### 4. 定时任务不执行

确保启动了 TaskIQ Scheduler：
```bash
taskiq scheduler -m app.core.taskiq:scheduler
```

### 5. 死信未保存到数据库

检查数据库连接配置，确保 `dead_letter_records` 表已创建。