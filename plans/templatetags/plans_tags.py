from datetime import datetime

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу."""
    return dictionary.get(key)


@register.filter
def attr(obj, attr_name):
    """Получить атрибут объекта по имени."""
    return getattr(obj, attr_name)


@register.filter
def format_date(year, month, day):
    """Форматировать дату в формат YYYY-MM-DD."""
    return f"{year}-{month:02d}-{day:02d}"


@register.simple_tag
def get_date_key(year, month, day):
    """Форматирует дату в строку формата YYYY-MM-DD."""
    return f"{year:04d}-{month:02d}-{day:02d}"


@register.filter
def get_shift_ids(plan):
    """Получает список ID смен из плана"""
    if isinstance(plan, dict):
        # Если план - это словарь (для существующих планов)
        shift_id = plan.get("shift_id")
        return [shift_id] if shift_id else []
    else:
        # Если план - это объект модели
        return [plan.shift.id] if plan.shift else []


@register.filter
def is_list(value):
    """Проверяет, является ли значение списком или QuerySet."""
    return isinstance(value, (list, tuple)) or hasattr(value, "__iter__")


@register.filter
def map(value, attr_path):
    """Применяет атрибут к каждому элементу списка."""
    if not is_list(value):
        return []

    result = []
    for item in value:
        try:
            # Разбиваем путь к атрибуту на части
            parts = attr_path.split(".")
            current = item
            for part in parts:
                current = getattr(current, part)
            result.append(current)
        except (AttributeError, TypeError):
            continue
    return result


@register.filter
def join(value, separator):
    """Объединяет элементы списка в строку с разделителем."""
    if not is_list(value):
        return str(value)
    return separator.join(str(item) for item in value)


@register.filter
def split(value, separator):
    """Разбивает строку на список по разделителю."""
    if not value:
        return []
    return [item.strip() for item in str(value).split(separator)]


@register.filter
def has_shift(plans, shift_id):
    """Проверяет, есть ли смена в списке планов."""
    if not is_list(plans):
        return plans.shift.id == shift_id

    for plan in plans:
        if plan.shift.id == shift_id:
            return True
    return False
