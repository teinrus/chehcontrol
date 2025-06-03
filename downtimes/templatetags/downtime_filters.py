from django import template

register = template.Library()

@register.filter
def filter_by_line(downtimes, line):
    """Фильтрует простои по линии"""
    return [d for d in downtimes if d.line == line] 