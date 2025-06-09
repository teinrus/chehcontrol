import logging

from django.apps import AppConfig

logger = logging.getLogger("app_task")


class AppTaskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app_task"

    def ready(self):
        try:
            from app_task.scheduler import start_scheduler

            start_scheduler()
        except Exception as e:
            logger.error(
                f"Failed to start scheduler in AppConfig.ready: {str(e)}", exc_info=True
            )
