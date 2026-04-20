"""
TaskIQ 定时任务定义

此文件演示如何使用 TaskIQ 的原生调度功能定义定时任务。

调度方式：
- @taskiq_task + @every(): Cron 表达式，如 "*/5 * * * *" 表示每5分钟
- @taskiq_task + @interval(): 固定间隔，支持 seconds/minutes/hours 参数
- @taskiq_task + @crontab(): 详细 Cron 参数
- add_schedule(): 手动添加任务
"""

import logging
from datetime import timedelta

from app.core.taskiq import taskiq_task
from app.core.taskiq_scheduler import every, interval, crontab, add_schedule

_logger = logging.getLogger(__name__)


@taskiq_task(queue="default", timeout=60)
@every("*/10 * * * *")  # 每10分钟执行
async def sync_market_data():
    """
    同步市场数据任务
    每10分钟从外部源同步最新的市场数据
    """
    _logger.info("开始执行市场数据同步任务")
    # TODO: 实现市场数据同步逻辑
    _logger.info("市场数据同步任务完成")
    return {"status": "success", "task": "sync_market_data"}


@taskiq_task(queue="default", timeout=300)
@interval(hours=1)  # 每小时执行
async def generate_daily_report():
    """
    生成每日报告任务
    每小时检查并生成当日的各类统计报告
    """
    _logger.info("开始生成每日报告")
    # TODO: 实现报告生成逻辑
    _logger.info("每日报告生成完成")
    return {"status": "success", "task": "generate_daily_report"}


@taskiq_task(queue="default", timeout=600)
@crontab(hour=9, minute=0)  # 每天9:00执行
async def morning_notification():
    """
    早间通知任务
    每天早上9点发送通知提醒
    """
    _logger.info("发送早间通知")
    # TODO: 实现通知发送逻辑
    return {"status": "success", "task": "morning_notification"}


@taskiq_task(queue="default", timeout=300)
@crontab(hour=18, minute=0)  # 每天18:00执行
async def evening_summary():
    """
    晚间汇总任务
    每天下午6点生成当日工作汇总
    """
    _logger.info("生成晚间汇总")
    # TODO: 实现汇总生成逻辑
    return {"status": "success", "task": "evening_summary"}


@taskiq_task(queue="default", timeout=1800)
@crontab(day_of_week="1", hour=0, minute=0)  # 每周一零点执行
async def weekly_data_cleanup():
    """
    周数据清理任务
    每周一凌晨清理过期数据
    """
    _logger.info("开始周数据清理")
    # TODO: 实现数据清理逻辑
    _logger.info("周数据清理完成")
    return {"status": "success", "task": "weekly_data_cleanup"}


# 使用 TaskIQ 的 add_schedule 手动添加任务
# 注意：这些任务需要在应用启动后通过调用 add_schedule 来注册

# 备份数据库任务的示例（手动注册）
async def register_backup_database():
    from app.core.taskiq_scheduler import add_schedule
    add_schedule(
        task_name="app.tasks.scheduled_tasks.backup_database_task",
        schedule="0 2 * * *",  # 每天凌晨2点
        name="backup_database",
        description="数据库备份任务"
    )


# 用户数据同步任务的示例（手动注册）
async def register_sync_user_data():
    from app.core.taskiq_scheduler import add_schedule
    from datetime import timedelta
    add_schedule(
        task_name="app.tasks.scheduled_tasks.sync_user_data_task",
        schedule=timedelta(minutes=30),  # 每30分钟
        name="sync_user_data",
        description="用户数据同步"
    )


@taskiq_task(queue="default", timeout=600)
async def backup_database_task():
    """
    数据库备份任务
    """
    _logger.info("开始数据库备份")
    # TODO: 实现数据库备份逻辑
    _logger.info("数据库备份完成")
    return {"status": "success", "task": "backup_database"}


@taskiq_task(queue="default", timeout=120)
async def sync_user_data_task():
    """
    用户数据同步任务
    """
    _logger.info("开始同步用户数据")
    # TODO: 实现用户数据同步逻辑
    _logger.info("用户数据同步完成")
    return {"status": "success", "task": "sync_user_data"}
