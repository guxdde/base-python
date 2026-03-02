import json
import logging
import asyncio
from typing import Optional, Callable, Any
from celery import Celery, signals, Task
from celery.exceptions import SoftTimeLimitExceeded
from kombu import Exchange, Queue, Producer, Connection
from urllib.parse import quote_plus

from .config import settings
from . import config as core_config
from . import database as core_database
from . import redis as core_redis
from . import logger as core_logger
from .task_registry import TaskRegistry, task_registry
from .beat import BeatScheduler, beat_scheduler
from .dead_letter import DeadLetterManager

_logger = logging.getLogger(__name__)


def _build_broker_url() -> str:
    """Build RabbitMQ AMQP URL from settings"""
    vh = settings.rabbitmq.virtual_host or "/"
    if not str(vh).startswith("/"):
        vh = f"/{vh}"
    user = settings.rabbitmq.username or ""
    password = settings.rabbitmq.password or ""
    host = settings.rabbitmq.host
    port = settings.rabbitmq.port
    user_enc = quote_plus(str(user))
    pass_enc = quote_plus(str(password))
    return f"amqp://{user_enc}:{pass_enc}@{host}:{port}{vh}"

def _build_broker_url_from_settings():
    """
    Try to obtain broker URL: prefer explicit celery.broker, fallback to existing builder if present.
    """
    try:
        return _build_broker_url()  # existing function in this file
    except Exception:
        # last-resort: try to use redis settings
        try:
            if settings.redis and settings.redis.url:
                return settings.redis.url
        except Exception:
            pass
    return None

class _CeleryApp:
    _app: Optional[Celery] = None

    def get_app(self):
        """
        Build or return a configured Celery app using project settings.
        """
        celery_settings = settings.celery
        broker_url = _build_broker_url_from_settings()
        result_backend = celery_settings.result_backend

        app = Celery(
            "app",
            broker=broker_url,
            backend=result_backend or None,
        )

        # base config from settings
        app.conf.update(
            task_acks_late=celery_settings.task_acks_late,
            worker_prefetch_multiplier=celery_settings.worker_prefetch_multiplier,
            task_default_queue=celery_settings.task_default_queue,
            task_default_delivery_mode=2,
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            task_soft_time_limit=celery_settings.default_soft_time_limit,
            task_time_limit=celery_settings.default_time_limit,
        )

        # Setup DLX + queues: create a default queue with DLX args
        try:
            dlx_conf = celery_settings.rabbitmq
            if dlx_conf.enabled:
                dlx_exchange = Exchange(dlx_conf.exchange, type="direct", durable=True)
                dlq_name = dlx_conf.queue
                dlq = Queue(name=dlq_name, exchange=dlx_exchange, routing_key=dlx_conf.routing_key, durable=True)
                # Main queue with dead-letter exchange args
                main_exchange = Exchange("celery", type="direct", durable=True)
                main_queue = Queue(
                    name=celery_settings.task_default_queue,
                    exchange=main_exchange,
                    routing_key=celery_settings.task_default_queue,
                    durable=True,
                    queue_arguments={
                        "x-dead-letter-exchange": dlx_exchange.name,
                        "x-dead-letter-routing-key": dlx_conf.routing_key,
                    },
                )
                app.conf.task_queues = (main_queue, dlq)
            else:
                # single queue
                main_exchange = Exchange("celery", type="direct", durable=True)
                main_queue = Queue(
                    name=celery_settings.task_default_queue,
                    exchange=main_exchange,
                    routing_key=celery_settings.task_default_queue,
                    durable=True,
                )
                app.conf.task_queues = (main_queue,)
        except Exception as e:
            _logger.exception("Failed to configure queues/DLX: %s", e)

        # beat schedule from settings OR code-defined schedules
        try:
            beat_conf = celery_settings.beat
            if beat_conf.enabled and isinstance(beat_conf.schedule, dict):
                app.conf.beat_schedule = beat_conf.schedule
            # Also load code-defined schedules from BeatScheduler
            code_schedule = beat_scheduler.get_schedule()
            if code_schedule:
                if not hasattr(app.conf, 'beat_schedule') or not app.conf.beat_schedule:
                    app.conf.beat_schedule = {}
                app.conf.beat_schedule.update(code_schedule)
                _logger.info(f"Loaded {len(code_schedule)} scheduled tasks from code")
        except Exception:
            pass

        # Attach signal handlers for resource injection and failure handling
        _attach_task_signals(app, settings, celery_settings)

        self._app = app
        return app

def _attach_task_signals(app: Celery, settings, celery_settings):
    @signals.task_prerun.connect
    def _task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
        # create db_session and redis_client and attach to request for use inside task
        try:
            # DB session factory: try common names defensively
            db_session = None
            if hasattr(core_database, "get_session"):
                db_session = core_database.get_session()
            elif hasattr(core_database, "SessionLocal"):
                db_session = core_database.SessionLocal()
            elif hasattr(core_database, "create_session"):
                db_session = core_database.create_session()
            # attach if possible
            if db_session is not None and hasattr(task, "request"):
                setattr(task.request, "db_session", db_session)
        except Exception:
            _logger.exception("Failed to create DB session for task %s", task_id)

        try:
            redis_client = None
            if hasattr(core_redis, "get_client"):
                redis_client = core_redis.get_client()
            elif hasattr(core_redis, "get_redis"):
                redis_client = core_redis.get_redis()
            elif hasattr(core_redis, "create_client"):
                redis_client = core_redis.create_client()
            if redis_client is not None and hasattr(task, "request"):
                setattr(task.request, "redis_client", redis_client)
        except Exception:
            _logger.exception("Failed to create redis client for task %s", task_id)

    @signals.task_postrun.connect
    def _task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra):
        # tear down DB session and redis client
        try:
            if hasattr(task, "request"):
                db_session = getattr(task.request, "db_session", None)
                if db_session is not None:
                    try:
                        if hasattr(db_session, "close"):
                            db_session.close()
                        elif hasattr(db_session, "remove"):
                            db_session.remove()
                    except Exception:
                        _logger.exception("Error closing db session for task %s", task_id)
        except Exception:
            _logger.exception("Unexpected error in task_postrun db cleanup")

        try:
            if hasattr(task, "request"):
                redis_client = getattr(task.request, "redis_client", None)
                # if redis_client has close/connection_pool, attempt to release
                try:
                    if hasattr(redis_client, "close"):
                        redis_client.close()
                except Exception:
                    # Some redis client implementations don't need explicit close
                    pass
        except Exception:
            _logger.exception("Unexpected error in task_postrun redis cleanup")

    @signals.task_failure.connect
    def _task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **extra):
        """
        On failure, save task metadata to database dead letter table.
        """
        try:
            task_name = getattr(sender, "name", None) if sender else None
            queue = kwargs.get('_queue') if kwargs else None
            worker = extra.get('hostname') if extra else None
            
            _logger.error(
                "Task %s failed: %s (task_name: %s, queue: %s)",
                task_id, str(exception), task_name, queue
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_save_failure_to_db(
                    task_id=task_id,
                    task_name=task_name,
                    args=args,
                    kwargs=kwargs,
                    exception=str(exception),
                    traceback=str(traceback) if traceback else None,
                    queue=queue,
                    worker=worker,
                ))
            finally:
                loop.close()
                
        except Exception:
            _logger.exception("Unhandled exception in task_failure handler for %s", task_id)


async def _save_failure_to_db(
    task_id: str,
    task_name: str,
    args: tuple = None,
    kwargs: dict = None,
    exception: str = None,
    traceback: str = None,
    queue: str = None,
    worker: str = None,
):
    """Save failure record to database."""
    try:
        db_session = None
        if hasattr(core_database, "get_session"):
            db_session = await core_database.get_session()
        elif hasattr(core_database, "dbm"):
            db_session = await core_database.dbm.get_session()
        
        if db_session is None:
            _logger.error("No database session available for saving dead letter")
            return
        
        manager = DeadLetterManager(db_session)
        
        celery_settings = settings.celery
        max_retries = getattr(celery_settings, 'max_retries', 3) if celery_settings else 3
        
        await manager.save_failure(
            task_id=task_id,
            task_name=task_name,
            args=args,
            kwargs=kwargs,
            exception=exception,
            traceback=traceback,
            queue=queue,
            worker=worker,
            max_retries=max_retries,
        )
        await db_session.close()
    except Exception:
        _logger.exception("Failed to save failure to database for task %s", task_id)


# Decorator to create tasks easily from code, supporting per-task timeouts and queue override
def celery_task(*dargs, queue: str = None, soft_time_limit: int = None, time_limit: int = None, 
                name: str = None, description: str = None, tags: list = None, **dkwargs):
    """
    Usage:
      @celery_task(queue='low', soft_time_limit=10, time_limit=20)
      def my_task(...):
          ...
    
    Auto-registers the task to TaskRegistry.
    """
    def _wrap(func):
        task_name = name or func.__name__
        
        # create task options merged with settings defaults
        defaults = settings.celery
        task_opts = {}
        if queue:
            task_opts["queue"] = queue
        # resolve soft/time limits
        task_opts["soft_time_limit"] = soft_time_limit or defaults.default_soft_time_limit
        task_opts["time_limit"] = time_limit or defaults.default_time_limit
        
        # Apply additional options
        for key, value in dkwargs.items():
            task_opts[key] = value

        # Get or create Celery app
        celery_app = None
        try:
            app_factory = globals().get("_celery_app_instance")
            if app_factory is not None:
                celery_app = app_factory.get_app()
        except Exception:
            pass
        
        if celery_app is None:
            broker = _build_broker_url_from_settings()
            celery_app = Celery("app_temp", broker=broker)

        # Register to TaskRegistry
        task_registry.register(
            name=task_name,
            func=func,
            queue=queue,
            soft_time_limit=task_opts.get("soft_time_limit"),
            time_limit=task_opts.get("time_limit"),
            options=task_opts,
            description=description,
            tags=tags or [],
        )
        
        # Apply as celery.task decorator
        return celery_app.task(**task_opts)(func)

    # support both @celery_task and @celery_task(...)
    if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
        return _wrap(dargs[0])
    return _wrap

# 兼容 Celery CLI 使用方式，暴露一个 module-level app
# Ensure a single _celery_app_instance placeholder for modules that import it
try:
    _celery_app_instance = _CeleryApp()
except Exception:
    _celery_app_instance = None
