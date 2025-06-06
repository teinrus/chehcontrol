from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from downtimes.models import Line, Shift

User = get_user_model()


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название продукции")
    description = models.TextField(blank=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Продукция"
        verbose_name_plural = "Продукция"
        ordering = ["name"]
        unique_together = ["name"]

    def __str__(self):
        return self.name


class Plan(models.Model):
    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("active", "Активен"),
        ("completed", "Завершен"),
        ("cancelled", "Отменен"),
    ]

    line = models.ForeignKey(
        Line, on_delete=models.CASCADE, related_name="plans", verbose_name="Линия"
    )
    shift = models.ForeignKey(
        Shift, on_delete=models.CASCADE, related_name="plans", verbose_name="Смена"
    )
    date = models.DateField(verbose_name="Дата")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="Статус"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_plans",
        verbose_name="Создал",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    notes = models.TextField(blank=True, verbose_name="Примечания")

    class Meta:
        verbose_name = "План производства"
        verbose_name_plural = "Планы производства"
        ordering = ["-date", "line", "shift"]
        unique_together = ["line", "shift", "date"]

    def __str__(self):
        return f"{self.line.name} - {self.shift.name} - {self.date}"

    def clean(self):
        if self.shift.line != self.line:
            raise ValidationError(
                {"shift": "Смена должна принадлежать выбранной линии"}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_total_planned(self):
        """Получить общее запланированное количество"""
        return sum(item.planned_quantity for item in self.items.all())

    def get_total_completed(self):
        """Получить общее выполненное количество"""
        return sum(item.completed_quantity for item in self.items.all())


class PlanItem(models.Model):
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="items", verbose_name="План"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="plan_items",
        verbose_name="Продукция",
    )
    planned_quantity = models.PositiveIntegerField(verbose_name="Плановое количество")
    completed_quantity = models.PositiveIntegerField(
        default=0, verbose_name="Выполнено"
    )
    notes = models.TextField(blank=True, verbose_name="Примечания")

    class Meta:
        verbose_name = "Позиция плана"
        verbose_name_plural = "Позиции плана"
        ordering = ["product"]

    def __str__(self):
        return f"{self.product.name} - {self.planned_quantity} шт."

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_completion_percentage(self):
        """Получить процент выполнения"""
        if self.planned_quantity == 0:
            return 0
        return (self.completed_quantity / self.planned_quantity) * 100
