import logging
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from downtimes.models import Downtime, Line
from users.models import CustomUser

from .models import Task

logger = logging.getLogger("app_task")


def get_system_user():
    """
    Получает системного пользователя с username='sys_user'
    """
    try:
        user = CustomUser.objects.get(username="sys_user", is_active=True)
        return user
    except CustomUser.DoesNotExist:
        logger.error("Системный пользователь 'sys_user' не найден или неактивен")
        return None


def check_existing_downtime(line, start_time):
    """
    Проверяет наличие существующего простоя в диапазоне времени
    """
    # Проверяем, нет ли уже активного простоя в диапазоне ±5 минут
    time_range = timezone.timedelta(minutes=5)
    existing_downtime = (
        Downtime.objects.filter(
            line=line,
            is_active=True,
            end_time__isnull=True,
            start_time__lte=start_time + time_range,
            start_time__gte=start_time - time_range,
        )
        .order_by("-start_time")
        .first()
    )

    if existing_downtime:
        logger.info(
            f"Found existing active downtime {existing_downtime.id} "
            f"for line {line.name} near {start_time}"
        )
        return existing_downtime

    # Дополнительная проверка на любой активный простой
    any_active_downtime = Downtime.objects.filter(
        line=line, is_active=True, end_time__isnull=True
    ).first()

    if any_active_downtime:
        logger.info(
            f"Found another active downtime {any_active_downtime.id} "
            f"for line {line.name}. Skipping creation"
        )
        return any_active_downtime

    return None


@transaction.atomic
def create_downtime(line, section, department, reason, start_time, notes):
    """
    Создает новый простой от имени системного пользователя
    """
    system_user = get_system_user()
    if not system_user:
        logger.error("Не удалось создать простой: системный пользователь не найден")
        return None

    try:
        # Проверяем наличие существующего простоя перед созданием
        existing_downtime = check_existing_downtime(line, start_time)
        if existing_downtime:
            logger.info(
                f"Found existing downtime {existing_downtime.id} "
                f"for line {line.name}, skipping creation"
            )
            return existing_downtime

        # Используем select_for_update для блокировки строки
        with transaction.atomic():
            new_downtime = Downtime.objects.create(
                line=line,
                section=section,
                department=department,
                reason=reason,
                start_time=start_time,
                is_active=True,
                created_by=system_user,
                notes=notes,
            )
            logger.info(
                f"Successfully created new downtime {new_downtime.id} "
                f"for line {line.name}"
            )
            return new_downtime
    except Exception as e:
        logger.error(f"Failed to create new downtime: {str(e)}", exc_info=True)
        return None


def handle_shift_boundary(downtime, line):
    """
    Обрабатывает простой, пересекающий границу смены
    """
    current_time = timezone.now()
    current_shift = line.get_active_shift(current_time)

    if not current_shift:
        logger.warning(f"No active shift found for line {line.name}")
        return None

    # Получаем дату начала смены
    shift_date = current_time.date()

    # Определяем, когда началась текущая смена
    if current_shift.start_time > current_time.time():
        # Если время начала смены больше текущего времени,
        # значит смена началась вчера
        shift_date = shift_date - timezone.timedelta(days=1)

    # Создаем datetime для начала смены
    shift_start_time = timezone.make_aware(
        datetime.combine(shift_date, current_shift.start_time),
        timezone=timezone.get_current_timezone(),
    )

    logger.debug(
        f"Checking shift boundary for downtime {downtime.id}. "
        f"Downtime start: {downtime.start_time}, "
        f"Shift start: {shift_start_time}, "
        f"Current time: {current_time}, "
        f"Line: {line.name}"
    )

    # Проверяем, начался ли простой до начала текущей смены
    if downtime.start_time < shift_start_time:
        logger.info(
            f"Downtime {downtime.id} started before current shift. "
            f"Completing at shift boundary."
        )

        try:
            with transaction.atomic():
                # Блокируем строку для обновления
                downtime = Downtime.objects.select_for_update().get(pk=downtime.pk)

                # Завершаем текущий простой ровно на границе смены
                downtime.end_time = shift_start_time
                downtime.is_active = False
                downtime.save()

                # Проверяем, нет ли уже активного простоя
                if Downtime.objects.filter(
                    line=line, is_active=True, end_time__isnull=True
                ).exists():
                    logger.warning(
                        f"Active downtime already exists for line {line.name}, "
                        f"skipping new downtime creation"
                    )
                    return downtime

                # Создаём новый простой только если нет активного
                new_downtime = create_downtime(
                    line=line,
                    section=downtime.section,
                    department=downtime.department,
                    reason=downtime.reason,
                    start_time=shift_start_time,
                    notes=(
                        f"Automatically created from downtime {downtime.id}. "
                        f"Reason: shift boundary crossing"
                    ),
                )

                if new_downtime:
                    logger.info(
                        f"Created new downtime {new_downtime.id} " f"at shift boundary"
                    )
                    return new_downtime
                else:
                    logger.error("Failed to create new downtime at shift boundary")
                    return downtime
        except Exception as e:
            logger.error(f"Error handling shift boundary: {str(e)}", exc_info=True)
            return downtime
    else:
        logger.debug(
            f"Downtime {downtime.id} started after shift start - " f"no split needed"
        )
        return downtime


def create_or_get_task(name):
    """
    Создает новую задачу или возвращает существующую
    """
    running_task = Task.objects.filter(
        name=name, status__in=["pending", "running"]
    ).first()

    if running_task:
        logger.warning(
            f"Task {name} is already running or pending. "
            f"Created at {running_task.created_at}"
        )
        return running_task

    return Task.objects.create(
        name=name,
        status="pending",
        description=f"Task {name} created at {timezone.now()}",
    )


def run_task(task_name, task_func):
    """
    Выполняет задачу с отслеживанием статуса
    """
    task = create_or_get_task(task_name)

    try:
        logger.info(f"Starting task: {task_name}")
        task.status = "running"
        task.started_at = timezone.now()
        task.save()

        result = task_func()
        task.status = "completed"
        task.result = str(result)
        logger.info(f"Task {task_name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Task {task_name} failed with error: {str(e)}", exc_info=True)
        task.status = "failed"
        task.error_message = str(e)
        raise
    finally:
        task.completed_at = timezone.now()
        task.save()


def process_last_downtimes():
    """
    Собирает информацию о последних простоях по каждой активной линии
    """
    return run_task("Last Downtimes Task", _process_last_downtimes)


def _process_last_downtimes():
    """
    Внутренняя функция для обработки простоев
    """
    logger.debug("Starting LastDowntimesTask execution")
    active_lines = Line.objects.filter(is_active=True)
    logger.debug(f"Found {active_lines.count()} active lines")
    result = []

    for line in active_lines:
        try:
            # Получаем последний простой для линии
            logger.debug(f"Searching for active downtimes for line {line.name}")
            last_downtime = (
                Downtime.objects.filter(
                    Q(line=line, is_active=True) | Q(line=line, end_time__isnull=True)
                )
                .order_by("-start_time")
                .first()
            )

            if last_downtime:
                logger.debug(
                    f"Found downtime {last_downtime.id} for line {line.name}. "
                    f"Active: {last_downtime.is_active}, "
                    f"Start: {last_downtime.start_time}, "
                    f"End: {last_downtime.end_time}"
                )
                # Проверяем и обрабатываем пересечение границы смены
                last_downtime = handle_shift_boundary(last_downtime, line)

                if last_downtime:
                    line_info = {
                        "line_name": line.name,
                        "downtime_start": last_downtime.start_time.strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                        "duration": last_downtime.get_duration(),
                        "section": str(last_downtime.section or "Не указан"),
                        "department": str(last_downtime.department or "Не указан"),
                        "reason": str(last_downtime.reason or "Не указана"),
                        "notes": last_downtime.notes or "Нет примечаний",
                    }
                    result.append(line_info)
                    logger.debug(f"Found downtime for line {line.name}: {line_info}")
            else:
                logger.debug(f"No active downtimes found for line {line.name}")
        except Exception as e:
            logger.error(f"Error processing line {line.name}: {str(e)}", exc_info=True)
            continue

    logger.debug(f"LastDowntimesTask completed. Found {len(result)} downtimes")
    return result
