"""
TaskIQ scheduler implementation.

This module provides a simplified scheduler interface that replaces
the custom BeatScheduler functionality, using TaskIQ's native scheduling.
"""

import logging
from datetime import timedelta
from functools import wraps
from typing import Callable, Optional, Union

from taskiq import TaskiqState
from taskiq.schedule_sources import CronScheduleSource
from taskiq.schedulers.scheduler import Scheduler

from .config import settings
from .taskiq import redis_broker, taskiq_app

_logger = logging.getLogger(__name__)


# Global scheduler instance
scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    """
    Get or create the global scheduler instance.

    Returns:
        Scheduler instance
    """
    global scheduler
    if scheduler is None:
        scheduler = Scheduler(broker=redis_broker)
    return scheduler


def init_scheduler() -> Scheduler:
    """
    Initialize and return the scheduler.

    Returns:
        Scheduler instance
    """
    global scheduler
    scheduler = get_scheduler()

    # Start the scheduler
    if not scheduler.is_running:
        scheduler.start()
        _logger.info("TaskIQ scheduler started")

    return scheduler


# Decorator for scheduled tasks (replaces BeatScheduler.every)
def every(cron_expression: str):
    """
    Decorator to schedule a task using cron expression.

    Args:
        cron_expression: Cron expression (e.g., "*/10 * * * *")

    Usage:
        @taskiq_task(queue="default")
        @every("*/10 * * * *")
        async def my_task():
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        # Register the task with TaskIQ
        task_func = taskiq_app.task()(wrapper)

        # Add to scheduler
        scheduler = get_scheduler()
        scheduler.add_source(
            CronScheduleSource(
                schedule_name=f"{func.__name__}_schedule",
                task_name=task_func.taskiq_name,
                cron=cron_expression,
            )
        )

        _logger.info(f"Scheduled task {func.__name__} with cron '{cron_expression}'")
        return wrapper

    return decorator


# Decorator for interval scheduling (replaces BeatScheduler.interval)
def interval(
    seconds: int = None,
    minutes: int = None,
    hours: int = None,
):
    """
    Decorator to schedule a task at fixed intervals.

    Args:
        seconds: Interval in seconds
        minutes: Interval in minutes
        hours: Interval in hours

    Usage:
        @taskiq_task(queue="default")
        @interval(hours=1)
        async def my_task():
            pass
    """
    # Calculate total seconds
    total_seconds = 0
    if seconds:
        total_seconds += seconds
    if minutes:
        total_seconds += minutes * 60
    if hours:
        total_seconds += hours * 3600

    if total_seconds == 0:
        raise ValueError("At least one of seconds, minutes, or hours must be specified")

    # Convert to cron expression
    if total_seconds < 3600:  # Less than 1 hour
        cron_expression = f"*/{total_seconds // 60} * * * *"
    else:  # 1 hour or more
        cron_expression = f"0 */{total_seconds // 3600} * * *"

    return every(cron_expression)


# Decorator for detailed crontab scheduling (replaces BeatScheduler.crontab)
def crontab(
    minute: str = "*",
    hour: str = "*",
    day_of_month: str = "*",
    month: str = "*",
    day_of_week: str = "*",
):
    """
    Decorator for detailed cron scheduling.

    Args:
        minute: Minute field (0-59)
        hour: Hour field (0-23)
        day_of_month: Day of month field (1-31)
        month: Month field (1-12 or JAN-DEC)
        day_of_week: Day of week field (0-7 or SUN-SAT)

    Usage:
        @taskiq_task(queue="default")
        @crontab(hour=9, minute=0)  # Every day at 9:00
        async def morning_task():
            pass
    """
    cron_expression = f"{minute} {hour} {day_of_month} {month} {day_of_week}"
    return every(cron_expression)


# Helper function to manually add schedules (replaces BeatScheduler.add)
def add_schedule(
    task_name: str,
    schedule: Union[str, timedelta],
    name: Optional[str] = None,
    description: Optional[str] = None,
):
    """
    Manually add a task schedule.

    Args:
        task_name: Name of the task to schedule
        schedule: Either a cron expression string or a timedelta interval
        name: Optional schedule name
        description: Optional schedule description

    Usage:
        add_schedule("my_task", "*/10 * * * *", name="my_schedule")
        add_schedule("my_task", timedelta(minutes=30), name="my_interval")
    """
    scheduler = get_scheduler()

    if isinstance(schedule, timedelta):
        # Convert timedelta to cron expression
        total_seconds = int(schedule.total_seconds())
        if total_seconds < 3600:
            cron_expression = f"*/{total_seconds // 60} * * * *"
        else:
            cron_expression = f"0 */{total_seconds // 3600} * * *"
    else:
        cron_expression = schedule

    schedule_name = name or f"{task_name}_schedule"

    scheduler.add_source(
        CronScheduleSource(
            schedule_name=schedule_name,
            task_name=task_name,
            cron=cron_expression,
        )
    )

    _logger.info(f"Added schedule '{schedule_name}' for task '{task_name}'")
    return schedule_name


# Function to get all scheduled tasks
def get_schedules():
    """
    Get all scheduled tasks.

    Returns:
        List of schedule information
    """
    scheduler = get_scheduler()
    schedules = []

    for source in scheduler.sources:
        if isinstance(source, CronScheduleSource):
            schedules.append({
                "name": source.schedule_name,
                "task": source.task_name,
                "cron": source.cron,
            })

    return schedules


# Function to remove a schedule
def remove_schedule(schedule_name: str):
    """
    Remove a scheduled task.

    Args:
        schedule_name: Name of the schedule to remove
    """
    scheduler = get_scheduler()

    # Remove the source
    scheduler.sources = [
        source for source in scheduler.sources
        if not (isinstance(source, CronScheduleSource) and
                source.schedule_name == schedule_name)
    ]

    _logger.info(f"Removed schedule '{schedule_name}'")


# Context manager for scheduler lifecycle
class SchedulerContext:
    """Context manager for scheduler lifecycle."""

    def __init__(self):
        self.scheduler = None

    async def __aenter__(self):
        self.scheduler = init_scheduler()
        return self.scheduler

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.scheduler and self.scheduler.is_running:
            self.scheduler.terminate()
            _logger.info("TaskIQ scheduler stopped")


# Export for easy import
__all__ = [
    "scheduler",
    "get_scheduler",
    "init_scheduler",
    "every",
    "interval",
    "crontab",
    "add_schedule",
    "get_schedules",
    "remove_schedule",
    "SchedulerContext",
]