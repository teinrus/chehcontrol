import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app_task.downtime_tasks import print_lines_and_shifts

logger = logging.getLogger("app_task")

_scheduler = None


def start_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler is already running")
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        print_lines_and_shifts,
        trigger=IntervalTrigger(seconds=60),
        id="print_lines_and_shifts_job",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: print_lines_and_shifts will run every 20 seconds.")


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler shutdown successfully")
