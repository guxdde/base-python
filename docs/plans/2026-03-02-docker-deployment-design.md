# Docker 部署方案设计

## 1. 项目概述

本项目采用 Docker 容器化部署，将基础设施组件与应用服务分离为两个独立的 compose 文件，便于环境管理和扩展。

### 部署模式
- 开发/测试环境：模拟生产状态
- 单机部署：100 QPS 以下

---

## 2. 架构设计

```
                    ┌─────────────────┐
                    │   OpenResty     │
                    │  (反向代理/网关)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐   ┌──────────┐
        │  FastAPI │  │  Celery  │   │  Celery  │
        │   API    │  │  Worker  │   │   Beat   │
        └────┬─────┘  └────┬─────┘   └──────────┘
             │             │
             └─────────────┼─────────────┐
                           │             │
                           ▼             ▼
                    ┌──────────┐   ┌──────────┐
                    │RabbitMQ  │   │   Redis  │
                    │(Broker)  │   │ (Cache)  │
                    └──────────┘   └──────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ PostgreSQL   │
                    │(TimescaleDB) │
                    └──────────────┘
```

---

## 3. 组件选型及版本

| 组件 | 版本 | 说明 |
|------|------|------|
| **Redis** | 7.2-alpine | 轻量、稳定，用于缓存/会话 |
| **PostgreSQL** | 17.5-timescaledb | 时序数据库扩展 |
| **RabbitMQ** | 3.12-management-alpine | Celery Broker，含管理界面 |
| **OpenResty** | 1.25-alpine | Nginx + Lua，支持动态配置 |
| **Python** | 3.12-slim | 应用运行环境 |
| **FastAPI** | latest | ASGI Web 框架 |
| **Celery** | 5.3 | 分布式任务队列 |

### RabbitMQ 插件
- `rabbitmq_management` - Web 管理界面
- `rabbitmq_delayed_message_exchange` - 延迟队列

---

## 4. 目录结构

```
project/
├── deploy/
│   ├── infra.yml              # 基础设施编排
│   ├── app.yml                # 应用服务编排
│   ├── .env.example           # 环境变量模板
│   ├── .env                   # 环境变量（不提交）
│   ├── nginx/
│   │   └── conf.d/
│   │       └── default.conf   # OpenResty 配置
│   └── logs/                  # 日志目录（可选）
├── src/                       # 应用代码
└── docs/
    └── plans/                 # 设计文档
        └── 2026-03-02-docker-deployment-design.md
```

---

## 5. 基础设施配置 (infra.yml)

### 5.1 Redis
```yaml
redis:
  image: redis:7.2-alpine
  container_name: app-redis
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

### 5.2 PostgreSQL + TimescaleDB
```yaml
postgres:
  image: timescale/timescaledb:2.15.0-pg17.5-alpine
  container_name: app-postgres
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-app}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    POSTGRES_DB: ${POSTGRES_DB:-appdb}
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
  restart: unless-stopped
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-app}"]
    interval: 10s
    timeout: 3s
    retries: 3
```

### 5.3 RabbitMQ
```yaml
rabbitmq:
  image: rabbitmq:3.12-management-alpine
  container_name: app-rabbitmq
  environment:
    RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-admin}
    RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-changeme}
    RABBITMQ_DEFAULT_VHOST: /
  ports:
    - "5672:5672"   # AMQP
    - "15672:15672" # Management UI
  volumes:
    - rabbitmq_data:/var/lib/rabbitmq
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

---

## 6. 应用服务配置 (app.yml)

### 6.1 OpenResty (反向代理)
```yaml
openresty:
  image: openresty/openresty:1.25-alpine
  container_name: app-nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/conf.d:/etc/nginx/conf.d
    - ./nginx/html:/usr/share/nginx/html
  depends_on:
    - fastapi
  restart: unless-stopped
```

### 6.2 FastAPI
```yaml
fastapi:
  build:
    context: ../src
    dockerfile: Dockerfile
  container_name: app-fastapi
  env_file:
    - .env
  ports:
    - "8000:8000"
  volumes:
    - ../src:/app
  depends_on:
    redis:
      condition: service_healthy
    postgres:
      condition: service_healthy
    rabbitmq:
      condition: service_healthy
  command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  restart: unless-stopped
```

### 6.3 Celery Worker
```yaml
celery-worker:
  build:
    context: ../src
    dockerfile: Dockerfile
  container_name: app-celery-worker
  env_file:
    - .env
  volumes:
    - ../src:/app
  depends_on:
    - rabbitmq
    - redis
    - postgres
  command: celery -A worker worker --loglevel=info --concurrency=6 -n worker1@%h
  restart: unless-stopped
```

### 6.4 Celery Beat (定时任务)
```yaml
celery-beat:
  build:
    context: ../src
    dockerfile: Dockerfile
  container_name: app-celery-beat
  env_file:
    - .env
  volumes:
    - ../src:/app
  depends_on:
    - rabbitmq
    - redis
    - postgres
  command: celery -A worker beat --loglevel=info
  restart: unless-stopped
```

---

## 7. OpenResty 配置

### 7.1 主配置文件 (default.conf)

```nginx
upstream fastapi {
    server fastapi:8000;
}

server {
    listen 80;
    server_name localhost;

    # 静态文件
    location /static {
        alias /usr/share/nginx/html/static;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # API 代理
    location /api/ {
        proxy_pass http://fastapi/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 频率限制（滑动窗口）
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        
        proxy_pass http://fastapi/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

### 7.2 扩展配置（可选）

后续可根据需要添加：
- Lua 脚本实现复杂限流逻辑
- WAF 防护规则
- 响应缓存策略
- SSL/TLS 终端

---

## 8. 环境变量配置

### .env.example

```bash
# PostgreSQL
POSTGRES_USER=app
POSTGRES_PASSWORD=changeme
POSTGRES_DB=appdb
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# RabbitMQ
RABBITMQ_USER=admin
RABBITMQ_PASSWORD=changeme
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_VHOST=/

# Celery
CELERY_BROKER_URL=amqp://admin:changeme@rabbitmq:5672/
CELERY_RESULT_BACKEND=redis://redis:6379/0

# FastAPI
APP_ENV=production
LOG_LEVEL=info
SECRET_KEY=changeme
```

---

## 9. 使用说明

### 9.1 启动基础设施
```bash
cd deploy
cp .env.example .env
# 编辑 .env 配置实际值

docker-compose -f infra.yml up -d
```

### 9.2 启动应用服务
```bash
docker-compose -f app.yml up -d
```

### 9.3 统一启动（推荐）
```bash
# 创建统一的 docker-compose.yml
docker-compose -f infra.yml -f app.yml up -d
```

### 9.4 停止服务
```bash
# 停止应用
docker-compose -f app.yml down

# 停止基础设施（数据会保留）
docker-compose -f infra.yml down

# 停止并删除数据卷
docker-compose -f infra.yml down -v
```

### 9.5 查看日志
```bash
# 所有服务
docker-compose -f infra.yml -f app.yml logs -f

# 指定服务
docker-compose -f app.yml logs -f fastapi
docker-compose -f app.yml logs -f celery-worker
```

### 9.6 访问地址

| 服务 | 地址 |
|------|------|
| API | http://localhost/api/ |
| RabbitMQ Management | http://localhost:15672 |
| OpenResty Status | http://localhost/nginx_status |

---

## 10. 后续扩展建议

### 10.1 可选：MySQL 支持
如需复用现有 MySQL RDS，可添加：
```yaml
mysql:
  image: mysql:8.0
  # 配置连接外部 RDS
```

### 10.2 监控
- 添加 Prometheus + Grafana
- RabbitMQ 自带 Prometheus 插件

### 10.3 日志收集
- 挂载日志目录到宿主机
- 集成 ELK/Loki

### 10.4 高可用
- Celery Worker 多容器部署
- 使用 Docker Swarm 或 Kubernetes

---

## 11. 技术选型说明

### 11.1 OpenResty vs Nginx
选择 OpenResty 因为：
- 支持 Lua 脚本，扩展灵活
- 可实现复杂限流、缓存、WAF
- 向后兼容 Nginx
- 适合后期集群化扩展

### 11.2 RabbitMQ vs Redis (Celery Broker)
选择 RabbitMQ 因为：
- 完善的消息确认机制 (Ack)
- 支持延迟队列（插件）
- 更高的可靠性
- 适合生产环境

### 11.3 PostgreSQL + TimescaleDB
- 支持时序数据（TimescaleDB 扩展）
- 与 MySQL RDS 用途不同（时序 vs 关系）
- 17.5 版本与生产环境一致
