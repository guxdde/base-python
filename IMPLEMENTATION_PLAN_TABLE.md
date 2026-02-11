# IMPLEMENTATION PLAN TABLE (1-4: MVP核心实现)

以下表格列出 1-4 项的逐步实现任务、涉及的文件、验收标准、依赖关系和负责人，方便在 PR 评审阶段快速把控进度与落地节奏。

| Task ID | Area / Subsystem | Description | Affected Files / Modules | Type | Dependencies | Acceptance Criteria | Owner | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| T1-DBBind | Data Persistence / Multi-DB Bind | 引入多数据库绑定框架，PostgreSQL 为主库，准备 MySQL 接入路径 | app/db/binds.py; app/db/postgres.py; app/alembic/env.py | New | None | 1) BindManager 可注册新绑定 2) get_session(bind_name) 提供 AsyncSession 生成器 3) health 端点可注入 Session 并正常工作 | Dev-DB | planned | 后续接入具体模型与迁移脚本 |
| T2-TaskAPI | Task API Skeleton | 提供统一的任务注册 API，列出已注册、注册新任务、触发任务、查询状态 | app/api/v1/endpoints/tasks.py; tests/test_tasks_api.py | Update | T1 | 1) /api/v1/tasks/registered 返回注册名称列表 2) /api/v1/tasks/register/ /run 已可用 3) /tasks/{task_id} 返回状态 | Dev-TA | in_progress | 与 Celery 的实际任务绑定对接时升级 |
| T3-JWT | JWT 认证初版 | 提供 token 颁发与校验入口，用户登录接口 | app/auth/jwt.py; app/auth/auth.py; app/main.py; tests/test_jwt_auth.py | New | None | 1) /auth/login 返回有效 JWT 2) /auth/verify 验证并返回用户信息 3) /api/v1/secure/ping 需令牌才能访问 | Dev-Auth | in_progress | 未来接入刷新策略 |
| T4-Logging | 日志与观测 | 引入结构化日志输出、LoggerAdapter、健康端点日志记录 | app/common/logging_utils.py; app/api/v1/endpoints/health.py | Update | T3 | 1) health 日志输出为 JSON 结构，带 trace_id（如有） 2) 统一日志 API 供未来追踪/指标接入 | Dev-Obs | done | 与 Prometheus/OpenTelemetry 的集成待后续 | 

## 里程碑与验收
- 验收点 1：骨架能启动并通过 /health、/config、/tasks/registered 等端点验证
- 验收点 2：BindManager 可注册新数据库连接，health 端点能通过注入的 Session 做简单查询
- 验收点 3：JWT 登录/校验工作流可跑通，受保护路由可按权限访问
- 验收点 4：日志输出为结构化日志，能在日志聚合端点正确呈现

注释
- 实施过程中如遇到接口变更、字段命名冲突等，优先保持向后兼容性，并在 PR 描述中注明变更原因。
