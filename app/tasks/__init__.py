"""
定时任务模块

此模块用于定义 Celery 定时任务。
定时任务通过 BeatScheduler 装饰器注册，会在应用启动时自动加载。

定义方式：
1. 使用 @BeatScheduler.every() - Cron 表达式
2. 使用 @BeatScheduler.interval() - 固定间隔
3. 使用 @BeatScheduler.crontab() - 详细 Cron 参数
4. 使用 BeatScheduler.add() - 手动添加
"""

from app.tasks import scheduled_tasks  # noqa: F401 导入即注册定时任务
