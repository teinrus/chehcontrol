import logging

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.utils import timezone

from app_task.downtime_tasks import process_last_downtimes

logger = logging.getLogger("app_task")

# Глобальная переменная для хранения экземпляра планировщика
_scheduler = None


def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} executed successfully")


def start_scheduler():
    global _scheduler

    # Проверяем, не запущен ли уже планировщик
    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler is already running")
        return

    try:
        # Настройка планировщика
        jobstores = {
            "default": SQLAlchemyJobStore(
                url="sqlite:///jobs.sqlite", tablename="apscheduler_jobs"
            )
        }
        executors = {"default": ThreadPoolExecutor(20)}
        job_defaults = {
            "coalesce": True,  # Объединяем пропущенные запуски
            "max_instances": 1,  # Только один экземпляр задачи
            "misfire_grace_time": 30,  # Разрешаем выполнение с задержкой до 30 секунд
        }

        _scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=settings.TIME_ZONE,
        )

        # Добавляем слушатель событий
        _scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

        # Добавляем задачу
        _scheduler.add_job(
            process_last_downtimes,
            trigger=IntervalTrigger(
                seconds=12,  # Запускаем каждые 12 секунд для отладки
                start_date=timezone.now(),  # Начинаем с текущего момента
            ),
            id="last_downtimes_job",
            replace_existing=True,
            next_run_time=timezone.now(),  # Запускаем сразу
        )

        # Запускаем планировщик
        _scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {str(e)}", exc_info=True)
        raise


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler shutdown successfully")
