"""
TaskIQ 定时任务模块

此模块用于定义 TaskIQ 定时任务。
定时任务通过 @taskiq_task + 调度装饰器注册，会在应用启动时自动加载。

定义方式：
1. 使用 @taskiq_task + @every() - Cron 表达式
2. 使用 @taskiq_task + @interval() - 固定间隔
3. 使用 @taskiq_task + @crontab() - 详细 Cron 参数
4. 使用 add_schedule() - 手动添加
"""

from app.tasks import scheduled_tasks  # noqa: F401 导入即注册定时任务

# 在应用启动时注册手动添加的任务
async def register_manual_schedules():
    """注册手动添加的定时任务"""
    from app.core.taskiq_scheduler import add_schedule

    # 注册备份任务
    add_schedule(
        task_name="app.tasks.scheduled_tasks.backup_database_task",
        schedule="0 2 * * *",  # 每天凌晨2点
        name="backup_database",
        description="数据库备份任务"
    )
    _logger.info("手动任务 'backup_database' 已注册")

    # 注册用户数据同步任务
    from datetime import timedelta
    add_schedule(
        task_name="app.tasks.scheduled_tasks.sync_user_data_task",
        schedule=timedelta(minutes=30),  # 每30分钟
        name="sync_user_data",
        description="用户数据同步"
    )
    _logger.info("手动任务 'sync_user_data' 已注册")
