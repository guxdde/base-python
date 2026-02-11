# design.md — 框架代码架构设计（MVP：PostgreSQL 优先 + Redis/Celery）

## 1. 目标与范围
- MVP 目标：快速生成并验证一个可扩展的后端框架骨架，面向 AI 应用的网站开发。使用 FastAPI（异步）作为 Web 框架，PostgreSQL 为主数据库，未来可选 MySQL；支持多数据库连接，SQLAlchemy 的异步 ORM；Alembic 实现多数据库迁移。Redis 做统一缓存，Celery + RabbitMQ 实现后台任务与定时任务，死信与延时队列，并提供统一的任务注册表 API。用户层采用 JWT，租户层采用 OAuth（后续扩展）。部署以 Docker Compose 作为初始方案，框架通过配置注入连接信息。
- MVP 边界：完成组件接入、日志结构、参数配置、统一任务注册 API，后续再逐步完善鉴权/权限等能力。

## 2. 架构概览
- Web 层: FastAPI，异步路由，依赖注入（Depends）管理数据库会话、缓存、认证等。
- 数据访问层 (DAL):
  - 多数据库连接管理：按配置维护一个 bind → AsyncEngine/AsyncSession 的映射。
  - ORM：SQLAlchemy 的异步 API；模型可按连接绑定继承不同的基础类。
  - Alembic：多数据库绑定与分区迁移支持。
- 缓存层: Redis 客户端封装（异步）、统一缓存入口，带重连与健康自愈。
- 任务与队列: Celery + RabbitMQ，Redis 作为结果后端；支持死信队列、延时队列、Beat 定时任务；提供统一的任务注册表 API。
- 认证与授权: 用户 JWT，租户 OAuth（后续扩展）。
- 日志与监控: 结构化日志、初步指标暴露，便于后续接入 Prometheus/OpenTelemetry。
- 部署与运行: Docker Compose 的最小可用部署方案，外部组件地址以配置方式接入。

## 3. 模块职责与接口设计

- app/api/
  - v1/endpoints/
    - health: GET /api/v1/health
    - config: GET /api/v1/config
    - tasks: 统一的任务注册/运行端点
      - GET /api/v1/tasks/registered
      - POST /api/v1/tasks/register
      - POST /api/v1/tasks/run
      - GET /api/v1/tasks/{task_id}
  - v1/models/
    - Pydantic 模型：请求/响应结构，字段校验与文档自动化。

- app/config/
  - settings.yaml / settings.py
    - databases: 主库与可选库（多数据库绑定）
    - redis: URL、连接池、超时、重连策略
    - celery: broker_url、result_backend、队列、路由、Beat
    - logging: level、format、destinations
    - auth: jwt_secret、token_expiry、oauth_endpoints
    - features: 开关标记

- app/db/
  - base.py: AsyncEngine/AsyncSession 管理，事务上下文
  - models/
    - base_postgres.py
    - base_mysql.py
    - __init__.py
    - ai_model.py
  - migrations/
    - alembic.ini
    - env.py
    - versions/

- app/redis/
  - client.py: AsyncRedisClient，连接与健康
  - cache.py: CacheClient，get/set/del/ttl，命名空间

- app/celery_worker/
  - celery_app.py: Celery 实例、队列、路由
  - tasks.py: 示例任务、@register_task 装饰器

- app/common/
  - exceptions.py
  - logging_utils.py
  - dependencies.py
  - utils.py

- tests/
  - unit/
  - integration/
  - contract/

## 4. 数据库与 ORM 设计要点
- 多数据库绑定：配置多个数据库连接（如 postgres_main、analytics_mysql 等），通过 bind 名创建 AsyncEngine/AsyncSession。
- 模型绑定：模型可按连接绑定继承不同的基础类（BasePostgres、BaseMysql）。
- Alembic：使用 binds 实现多数据库迁移，env.py 根据绑定分发 metadata。

- 示例代码要点（非实现，仅设计要点）
  - create_async_session(bind_name) -> AsyncSession
  - get_engine(bind_name) -> AsyncEngine
  - 模型注册时使用元数据中的 bind 信息决定绑定

## 5. Redis 缓存设计
- 统一封装 AsyncRedisClient，提供健康接口与重连能力。
- CacheClient 封装 get/set/delete/incr/exists/expire，支持 TTL、命名空间。
- 兜底策略：缓存不可用时回退到直连数据库查询路径。
- 指标：命中率、延迟、失败率等供监控接入。

## 6. Celery、RabbitMQ 与任务系统
- Broker: RabbitMQ； Backend: Redis。
- DLX/DLQ：死信队列配置，错误任务入死信。
- 延时队列：ETA/Countdown 或 Redis 后端延时能力。
- 统一任务注册表 API：注册、列出、触发、查询状态。
- Beat：定时任务调度（后续扩展）。
- 幂等与重试：任务幂等设计与去重方案。

## 7. 认证与鉴权初版设计
- 用户 JWT：签发、验证、刷新。
- 租户 OAuth：后续实现。
- 路由保护：基于 Depends 的鉴权中间件。

## 8. 验证计划
- 验证目标：框架骨架可用、可扩展、稳定。
- 级别：单元测试、集成测试、端到端测试。
- 验证用例：配置解析、多数据库会话、缓存、API、任务端点。

## 9. API 设计概要（RESTful、OpenAPI 自动化）
- 端点示例：
  - GET /api/v1/health
  - GET /api/v1/config
  - POST /api/v1/tasks/register
  - POST /api/v1/tasks/run
  - GET /api/v1/tasks/{task_id}
  - GET /api/v1/tasks/registered

## 10. 验收与部署简述
- 部署：Docker Compose 初始方案，现有组件外部地址注入。
- 监控：结构化日志、基础指标。
- 安全：JWT 与 OAuth 的后续扩展点。

## 11. 设计变更与评审要点
- 确认 MVP 的范围、优先级、风险点。
- 记录评审意见，确保骨架可落地实现。

---

## 附件：Prompts（Prompts.md）位置在 prompts.md，见下一节。
