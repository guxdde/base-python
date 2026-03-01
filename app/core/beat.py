import logging
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import timedelta
from croniter import croniter
import hashlib

_logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    name: str
    task: str
    schedule: Any
    options: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: Optional[str] = None


class BeatScheduler:
    _tasks: Dict[str, ScheduledTask] = {}

    @classmethod
    def _normalize_schedule(cls, schedule: Union[str, int, timedelta]) -> Any:
        from celery.schedules import crontab, timedelta
        
        if isinstance(schedule, str):
            if schedule.count(' ') >= 5 or '*' in schedule:
                parts = schedule.split()
                if len(parts) == 5:
                    minute, hour, day_month, month, day_week = parts
                    return crontab(
                        minute=minute,
                        hour=hour,
                        day_of_month=day_month,
                        month_of_year=month,
                        day_of_week=day_week
                    )
                elif len(parts) == 6:
                    second, minute, hour, day_month, month, day_week = parts
                    return crontab(
                        minute=minute,
                        hour=hour,
                        day_of_month=day_month,
                        month_of_year=month,
                        day_of_week=day_week
                    )
            raise ValueError(f"Invalid cron expression: {schedule}")
        elif isinstance(schedule, int):
            return timedelta(seconds=schedule)
        elif isinstance(schedule, timedelta):
            return schedule
        return schedule

    @classmethod
    def every(
        cls,
        schedule: Union[str, int, timedelta],
        name: Optional[str] = None,
        queue: Optional[str] = None,
        description: Optional[str] = None,
        enabled: bool = True,
        **options
    ):
        def decorator(func: Callable) -> Callable:
            task_name = name or func.__name__
            full_task_name = f"app.tasks.{func.__module__}.{func.__name__}"
            
            normalized_schedule = cls._normalize_schedule(schedule)
            
            task_options = options.copy()
            if queue:
                task_options['queue'] = queue
            
            scheduled_task = ScheduledTask(
                name=task_name,
                task=full_task_name,
                schedule=normalized_schedule,
                options=task_options,
                enabled=enabled,
                description=description or func.__doc__,
            )
            
            cls._tasks[task_name] = scheduled_task
            _logger.info(f"Scheduled task registered: {task_name} (schedule: {schedule})")
            
            return func
        return decorator

    @classmethod
    def interval(
        cls,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        name: Optional[str] = None,
        queue: Optional[str] = None,
        description: Optional[str] = None,
        enabled: bool = True,
        **options
    ):
        if seconds is None and minutes is None and hours is None:
            raise ValueError("At least one of seconds, minutes, or hours must be specified")
        
        total_seconds = 0
        if seconds:
            total_seconds += seconds
        if minutes:
            total_seconds += minutes * 60
        if hours:
            total_seconds += hours * 3600
        
        schedule = timedelta(seconds=total_seconds)
        
        def decorator(func: Callable) -> Callable:
            task_name = name or func.__name__
            full_task_name = f"app.tasks.{func.__module__}.{func.__name__}"
            
            task_options = options.copy()
            if queue:
                task_options['queue'] = queue
            
            scheduled_task = ScheduledTask(
                name=task_name,
                task=full_task_name,
                schedule=schedule,
                options=task_options,
                enabled=enabled,
                description=description or func.__doc__,
            )
            
            cls._tasks[task_name] = scheduled_task
            _logger.info(f"Scheduled task registered: {task_name} (interval: {total_seconds}s)")
            
            return func
        return decorator

    @classmethod
    def crontab(
        cls,
        minute: str = "*",
        hour: str = "*",
        day_of_month: str = "*",
        month_of_year: str = "*",
        day_of_week: str = "*",
        name: Optional[str] = None,
        queue: Optional[str] = None,
        description: Optional[str] = None,
        enabled: bool = True,
        **options
    ):
        from celery.schedules import crontab as celery_crontab
        
        schedule = celery_crontab(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            day_of_week=day_of_week
        )
        
        def decorator(func: Callable) -> Callable:
            task_name = name or func.__name__
            full_task_name = f"app.tasks.{func.__module__}.{func.__name__}"
            
            task_options = options.copy()
            if queue:
                task_options['queue'] = queue
            
            scheduled_task = ScheduledTask(
                name=task_name,
                task=full_task_name,
                schedule=schedule,
                options=task_options,
                enabled=enabled,
                description=description or func.__doc__,
            )
            
            cls._tasks[task_name] = scheduled_task
            _logger.info(f"Scheduled task registered: {task_name} (crontab)")
            
            return func
        return decorator

    @classmethod
    def add(
        cls,
        task_name: str,
        task: str,
        schedule: Union[str, int, timedelta],
        options: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        description: Optional[str] = None,
    ) -> ScheduledTask:
        normalized_schedule = cls._normalize_schedule(schedule)
        
        scheduled_task = ScheduledTask(
            name=task_name,
            task=task,
            schedule=normalized_schedule,
            options=options or {},
            enabled=enabled,
            description=description,
        )
        
        cls._tasks[task_name] = scheduled_task
        _logger.info(f"Scheduled task added: {task_name}")
        
        return scheduled_task

    @classmethod
    def remove(cls, task_name: str) -> bool:
        if task_name in cls._tasks:
            del cls._tasks[task_name]
            _logger.info(f"Scheduled task removed: {task_name}")
            return True
        return False

    @classmethod
    def enable(cls, task_name: str) -> bool:
        if task_name in cls._tasks:
            cls._tasks[task_name].enabled = True
            return True
        return False

    @classmethod
    def disable(cls, task_name: str) -> bool:
        if task_name in cls._tasks:
            cls._tasks[task_name].enabled = False
            return True
        return False

    @classmethod
    def get(cls, task_name: str) -> Optional[ScheduledTask]:
        return cls._tasks.get(task_name)

    @classmethod
    def all(cls) -> List[ScheduledTask]:
        return list(cls._tasks.values())

    @classmethod
    def get_enabled(cls) -> List[ScheduledTask]:
        return [t for t in cls._tasks.values() if t.enabled]

    @classmethod
    def get_schedule(cls) -> Dict[str, Any]:
        result = {}
        for task in cls._tasks.values():
            if task.enabled:
                result[task.name] = {
                    "task": task.task,
                    "schedule": task.schedule,
                    "options": task.options,
                }
        return result

    @classmethod
    def clear(cls) -> None:
        cls._tasks.clear()
        _logger.info("All scheduled tasks cleared")

    @classmethod
    def get_names(cls) -> List[str]:
        return list(cls._tasks.keys())


beat_scheduler = BeatScheduler()
