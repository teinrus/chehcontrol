from django.db import models
from django.utils import timezone


class Task(models.Model):
    STATUS_CHOICES = [
        ("pending", "Ожидает выполнения"),
        ("running", "Выполняется"),
        ("completed", "Завершена"),
        ("failed", "Ошибка"),
    ]

    name = models.CharField(max_length=255, verbose_name="Название задачи")
    description = models.TextField(blank=True, verbose_name="Описание")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Статус"
    )
    created_at = models.DateTimeField(
        default=timezone.now, verbose_name="Дата создания"
    )
    started_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Дата начала выполнения"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Дата завершения"
    )
    result = models.TextField(blank=True, verbose_name="Результат выполнения")
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")

    class Meta:
        verbose_name = "Фоновая задача"
        verbose_name_plural = "Фоновые задачи"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
