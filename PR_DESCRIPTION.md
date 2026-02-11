Title: feat(mvp): multi-db binding, unified task API, JWT auth skeleton, and logging/observability skeleton

Summary
- Implement MVP skeletons to fast-track foundation work for a RESTful FastAPI backend with PostgreSQL (primary) and optional multi-database binding, Redis caching, and Celery-based asynchronous task processing. Added a unified task registration API, JWT-based user authentication scaffold, and a logging/observability skeleton. Deployed as code-ready patches for PR merge.

What changed
- Multi-database binding (PostgreSQL priority)
  - Added: app/db/binds.py (BindManager) to manage per-bind engines/sessions
  - Enhanced: app/db/postgres.py to initialize default bind and provide bind-based sessions
  - Alembic env placeholder: app/alembic/env.py (prepare for multi-bind migrations)
  - Tests scaffolding: tests/test_db_bindings.py added
- Unified Task API (RESTful)
  - Added: app/api/v1/endpoints/tasks.py extended with TASK_REGISTRY and /tasks/registered
  - Tests scaffolding: tests/test_tasks_api.py
- JWT Auth skeleton
  - Added: app/auth/jwt.py (encode/decode JWT with HMAC-SHA256)
  - Added: app/auth/auth.py (get_current_user dependency)
  - Updated: app/main.py with /auth/login and /auth/verify endpoints and protected route
  - Added: app/api/v1/endpoints/secure.py (sample protected endpoint)
- Logging/Observability skeleton
  - Updated: app/common/logging_utils.py with get_logger(name, trace_id) returning a LoggerAdapter
  - Updated: app/api/v1/endpoints/health.py to emit structured logs on health checks
- Tests
  - Tests for DB binding skeletons, task API, JWT auth flow, and logging adapter added (tests/test_db_bindings.py, tests/test_tasks_api.py, tests/test_jwt_auth.py, tests/test_logging.py, and tests/test_tasks_api.py)

Rationale
- This MVP focuses on enabling rapid scaffold generation and verification, with a clear path to deeper integration (full multi-database migrations, real Redis caching, actual Celery-based task execution). RESTful API is the primary public surface, with authentication scaffolding ready for expansion.

Testing strategy
- Unit tests for isolated components (DB bind manager, cache wrappers, JWT utils)
- Integration tests for endpoints (health, config, tasks), with mocked DB sessions and mock token flows
- End-to-end test scaffolds for JWT login flow and protected endpoints

Validation steps
- Run pytest for unit/integration tests
- Start FastAPI server and exercise endpoints:
  - GET /api/v1/health
  - GET /api/v1/config
  - POST /api/v1/tasks/register
  - POST /api/v1/tasks/run
  - GET /api/v1/tasks/registered
  - POST /auth/login
  - GET /auth/verify with Authorization header
- Confirm logging outputs in structured JSON format
- Validate that startup does not crash with missing components (e.g., Redis/Celery not yet wired)

Backward compatibility
- This patch set introduces new modules and optional features behind configuration switches. Existing endpoints remain functional with placeholders; follow-up PRs will wire real implementations.

Security considerations
- JWT skeleton uses environment-based secret configuration; no hard-coded secrets
- OAuth scaffolding is prepared for expansion; no real OAuth endpoints implemented yet

Open questions for design review
- Do we want to replace in-memory TASK_REGISTRY with a persistent registry from the start, or keep an in-process store until Celery integration is complete?
- Validation of multi-database migration strategy (Alembic bindings) in a staged environment

Next steps (post-PR)
- Implement full multi-database schema and migrations (Alembic binds)
- Implement real Celery task execution, DLX/DLQ, and ETA-based scheduling
- Implement full OAuth tenant integration and RBAC
- Integrate OpenTelemetry/Prometheus for tracing and metrics

Author & reviewers notes
- This PR is intended as a foundation for rapid validation and subsequent detailed implementations.
- Please review for API surface clarity, naming consistency, and test coverage alignment with the team’s standards.
