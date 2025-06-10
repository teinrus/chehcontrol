import logging
from datetime import datetime, time, timedelta

import pytz
from django.contrib.auth import get_user_model
from django.utils.timezone import localtime, make_aware, now

from downtimes.models import Downtime, Line

logger = logging.getLogger("app_task")
User = get_user_model()

# Определяем московский часовой пояс
MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def is_current_shift(shift_start, shift_end, current_time):
    """Проверяет, является ли смена текущей"""
    # Если current_time уже является time объектом, используем его как есть
    if isinstance(current_time, time):
        current_time_obj = current_time
    else:
        current_time_obj = current_time.time()

    # Если смена переходит через полночь (например, 20:00 - 09:15)
    if shift_end < shift_start:
        return current_time_obj >= shift_start or current_time_obj <= shift_end
    # Если смена в пределах одного дня (например, 08:00 - 16:30)
    else:
        # Для времени 16:30 оно должно относиться к следующей смене
        if current_time_obj == shift_end:
            return False
        return shift_start <= current_time_obj < shift_end


def format_shift_time(shift_time, current_date):
    """Форматирует время смены с учетом текущей даты"""
    if not isinstance(shift_time, time):
        raise ValueError(f"Expected time object, got {type(shift_time)}")

    try:
        naive_dt = datetime.combine(current_date, shift_time)
        return make_aware(naive_dt)
    except Exception:
        raise


def get_shift_for_time(line, target_time):
    """Получает смену для указанного времени"""
    shifts = getattr(line, "shifts", None)
    if shifts is None:
        return None

    # Преобразуем время в московский часовой пояс
    if not isinstance(target_time, time):
        target_time = target_time.astimezone(MOSCOW_TZ)
        logger.debug(f"Время после преобразования в московский пояс: {target_time}")

    target_time_obj = target_time.time()
    logger.debug(f"Ищем смену для времени: {target_time_obj}")

    for shift in shifts.all():
        logger.debug(f"Проверяем смену {shift}: {shift.start_time} - {shift.end_time}")
        if is_current_shift(shift.start_time, shift.end_time, target_time_obj):
            logger.debug(f"Нашли смену: {shift}")
            return shift
    return None


def get_current_shift(line, current_datetime):
    """Получает текущую смену для линии"""
    return get_shift_for_time(line, current_datetime)


def should_end_downtime(downtime, current_shift):
    """Проверяет, нужно ли завершить простой"""
    if not current_shift:
        return False

    # Получаем дату начала простоя
    downtime_date = downtime.start_time.date()
    current_date = now().date()

    # Если простой начался в предыдущие сутки, завершаем его
    if downtime_date < current_date:
        return True

    # Проверяем, начался ли простой в другой смене
    # и не является ли время начала простоя временем начала текущей смены
    downtime_time = downtime.start_time.time()
    return (
        not is_current_shift(downtime_time, current_shift.end_time, downtime.start_time)
        and downtime_time != current_shift.start_time
    )


def get_shift_end_time(shift, start_date):
    """Получает время окончания смены с учетом перехода через полночь"""
    # Преобразуем start_date в datetime с сохранением временной зоны
    if isinstance(start_date, datetime):
        start_datetime = start_date
    else:
        # Если передан date, создаем datetime с временем 00:00
        start_datetime = datetime.combine(start_date, time(0, 0))
        # Добавляем временную зону, если её нет
        if start_datetime.tzinfo is None:
            start_datetime = make_aware(start_datetime)

    # Преобразуем время в московский часовой пояс для корректного сравнения
    local_start_time = start_datetime.astimezone(MOSCOW_TZ).time()
    logger.debug(
        f"Время начала простоя в московском поясе: {local_start_time}, "
        f"смена: {shift.start_time} - {shift.end_time}"
    )

    # Если смена начинается в 00:00, то она заканчивается в 08:00 того же дня
    if shift.start_time == time(0, 0):
        end_date = start_datetime.date()
    # Если смена заканчивается в 00:00, это означает конец следующего дня
    elif shift.end_time == time(0, 0):
        end_date = start_datetime.date() + timedelta(days=1)
    else:
        # Если время окончания смены меньше времени начала, значит смена переходит на следующий день
        if shift.end_time < shift.start_time:
            # Для смен, переходящих через полночь, проверяем время начала простоя
            if local_start_time >= shift.start_time:
                # Если простой начался после начала смены, он заканчивается на следующий день
                end_date = start_datetime.date() + timedelta(days=1)
            else:
                # Если простой начался до начала смены, он заканчивается в тот же день
                end_date = start_datetime.date()
        else:
            end_date = start_datetime.date()

    logger.debug(
        f"Определяем время окончания смены: "
        f"смена {shift}, дата начала {start_datetime}, "
        f"дата окончания {end_date}"
    )

    # Создаем datetime с временем окончания смены
    end_datetime = datetime.combine(end_date, shift.end_time)
    # Добавляем временную зону, если её нет
    if end_datetime.tzinfo is None:
        end_datetime = make_aware(end_datetime)
    # Преобразуем в московский часовой пояс
    return end_datetime.astimezone(MOSCOW_TZ)


def print_lines_and_shifts():
    lines = Line.objects.all()
    current_datetime = now().astimezone(
        MOSCOW_TZ
    )  # Преобразуем текущее время в московское
    current_date = current_datetime.date()

    # Получаем системного пользователя для создания простоев
    sys_user = User.objects.filter(username__iexact="sys_user").first()
    if not sys_user:
        logger.error(
            "Системный пользователь sys_user не найден. " "Доступные пользователи: %s",
            ", ".join(User.objects.values_list("username", flat=True)),
        )
        return

    for line in lines:
        logger.info(f"Линия: {line.name}")
        shifts = getattr(line, "shifts", None)
        if shifts is not None:
            for shift in shifts.all():
                if is_current_shift(shift.start_time, shift.end_time, current_datetime):
                    start_time = format_shift_time(shift.start_time, current_date)
                    end_time = format_shift_time(shift.end_time, current_date)
                    logger.info(
                        f"  Смена: {shift} (текущая) "
                        f"{localtime(start_time).strftime('%d.%m.%Y %H:%M')} - "
                        f"{localtime(end_time).strftime('%d.%m.%Y %H:%M')}"
                    )
                else:
                    logger.info(f"  Смена: {shift}")
        else:
            logger.info("  Нет информации о сменах")

        # Получаем последний активный простой для линии
        last_downtime = (
            Downtime.objects.filter(line=line, end_time__isnull=True)
            .order_by("-start_time")
            .first()
        )

        if last_downtime:
            # Проверяем, нужно ли завершить простой
            current_shift = get_current_shift(line, current_datetime)
            if current_shift and should_end_downtime(last_downtime, current_shift):
                # Получаем смену, в которой начался простой
                downtime_shift = get_shift_for_time(line, last_downtime.start_time)
                logger.debug(
                    f"Время начала простоя: {last_downtime.start_time.astimezone(MOSCOW_TZ)}, "
                    f"найденная смена: {downtime_shift}"
                )
                if downtime_shift:
                    # Завершаем простой окончанием смены, в которой он начался
                    # Используем дату из времени начала простоя
                    downtime_start = last_downtime.start_time.astimezone(MOSCOW_TZ)
                    end_time = get_shift_end_time(downtime_shift, downtime_start)
                    last_downtime.end_time = end_time
                    last_downtime.save()
                    logger.info(
                        f"  Простой завершен окончанием смены: "
                        f"{localtime(last_downtime.start_time)} - "
                        f"{localtime(last_downtime.end_time)}"
                    )

                    # Создаем новый простой, начинающийся с момента окончания предыдущего
                    # Преобразуем время в московский часовой пояс
                    moscow_time = end_time.astimezone(MOSCOW_TZ)
                    new_downtime = Downtime.objects.create(
                        line=line,
                        start_time=moscow_time,
                        end_time=None,
                        created_by=sys_user,
                    )
                    logger.info(
                        f"  Создан новый простой: "
                        f"{localtime(new_downtime.start_time)} - None"
                    )
            else:
                logger.info(
                    f"  Последний простой: {localtime(last_downtime.start_time)} - None"
                )
        else:
            logger.info("  Нет активных простоев")
