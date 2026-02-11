- Prompt A1：FastAPI MVP 框架骨架
  - 目标：生成一个 FastAPI 应用骨架，包含 PostgreSQL 主库的异步连接、AsyncSession、健康端点、基础路由与依赖注入、日志初始化。
  - 输出：app/ 目录结构、核心模块骨架、示例模型、测试骨架

- Prompt A2：多数据库绑定与 Alembic 配置
  - 目标：实现 PostgreSQL 主库 + 额外数据库（如 analytics_mysql）的 bind 机制；提供 AsyncEngine/AsyncSession 的管理器、示例模型、以及 Alembic env.py 的多绑定分派逻辑。
  - 输出：db/ 与 alembic/ 相关配置与示例脚本

- Prompt A3：Redis 缓存封装
  - 目标：生成一个 AsyncRedisClient 封装及 CacheClient，包含 connect/reconnect、get/set/del、TTL、命名空间以及简单的装饰器缓存。
  - 输出：redis/client.py、redis/cache.py 的骨架示例

- Prompt A4：Celery + RabbitMQ 的任务框架
  - 目标：生成 Celery 应用骨架，包含 broker 设置、backend、任务注册装饰器 @register_task、一个示例任务、死信与 ETA 示例。
  - 输出：celery_worker/celery_app.py、celery_worker/tasks.py

- Prompt A5：统一任务注册 API 的 OpenAPI 设计
  - 目标：生成 RESTful API 端点集合，用于注册、列出、触发和查询任务状态
  - 输出：app/api/v1/routers 与 models（Pydantic）、OpenAPI 端点草案

- Prompt A6：JWT + OAuth 初版安全设计
  - 目标：生成用户 JWT 生成/校验逻辑，以及租户 OAuth 的接口雏形
  - 输出：auth/ 的骨架实现与示例用法

- Prompt A7：日志与观测模板
  - 目标：生成结构化日志、统一日志格式、基础指标暴露点
  - 输出：logging_utils.py、metrics.py 的骨架

- Prompt A8：Docker Compose MVP 部署草案
  - 目标：生成一个最小可用的 docker-compose.yml，指向现有组件的外部地址
  - 输出：docker-compose.yml 的骨架与服务注释

- Prompt A9：测试用例骨架
  - 目标：生成单元测试与集成测试的骨架，覆盖配置加载、DB 会话、缓存、API、任务端点
  - 输出：tests/ 目录骨架与示例测试

- Prompt A10：错误处理与异常架构
  - 目标：生成统一的异常层级、错误响应结构与错误码映射
  - 输出：exceptions.py 结构草案

- Prompt A11：模型与 ORM 映射示例
  - 目标：生成一个简单的 Pydantic 模型与 SQLAlchemy ORM 映射，演示多数据库绑定的实体
  - 输出：models 与 schemas 的示例

- Prompt A12：多租户 API 设计（无实现）
  - 目标：生成租户鉴权与资源隔离的接口设计草案，便于后续实现
  - 输出：租户相关接口草案

- Prompt A13：代码结构与包路径建议
  - 目标：给出清晰的包结构、模块划分、命名规范与导入路径，便于代码生成的一致性
  - 输出：包结构示例与路径约定
