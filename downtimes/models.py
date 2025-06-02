from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, time

User = get_user_model()

class Line(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название линии')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Линия'
        verbose_name_plural = 'Линии'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_active_shift(self, dt=None):
        """
        Получить активную смену для указанного времени
        Если время не указано, используется текущее время
        """
        if dt is None:
            dt = timezone.now()
        
        current_time = dt.time()
        return self.shifts.filter(
            start_time__lte=current_time,
            end_time__gt=current_time
        ).first()


class Shift(models.Model):
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='shifts', verbose_name='Линия')
    name = models.CharField(max_length=100, verbose_name='Название смены')
    start_time = models.TimeField(verbose_name='Время начала')
    end_time = models.TimeField(verbose_name='Время окончания')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Смена'
        verbose_name_plural = 'Смены'
        ordering = ['start_time']
        unique_together = ('line', 'name')

    def __str__(self):
        return f"{self.name} ({self.line.name}) {self.start_time} - {self.end_time}"

    def clean(self):
        if not self.is_active:
            return

        # Проверка пересечений смен для той же линии
        overlapping_shifts = Shift.objects.filter(
            line=self.line,
            is_active=True
        ).exclude(pk=self.pk).filter(
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        )

        if overlapping_shifts.exists():
            raise ValidationError("Смена пересекается с другой сменой на этой линии.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Section(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название участка')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='sections', verbose_name='Линия')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Участок'
        verbose_name_plural = 'Участки'
        ordering = ['line', 'name']
        unique_together = ['name', 'line']

    def __str__(self):
        return f"{self.name} ({self.line.name})"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название подразделения')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активно')

    class Meta:
        verbose_name = 'Подразделение'
        verbose_name_plural = 'Подразделения'
        ordering = ['name']

    def __str__(self):
        return self.name


class DowntimeReason(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название причины')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='reasons', verbose_name='Подразделение')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Причина простоя'
        verbose_name_plural = 'Причины простоев'
        ordering = ['department', 'name']
        unique_together = ['name', 'department']

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class Downtime(models.Model):
    line = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='Линия')
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Участок')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Подразделение')
    reason = models.ForeignKey(DowntimeReason, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Причина')

    start_time = models.DateTimeField(verbose_name='Время начала')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='Время окончания')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_downtimes', verbose_name='Создал')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    notes = models.TextField(blank=True, verbose_name='Примечания')

    class Meta:
        verbose_name = 'Простой'
        verbose_name_plural = 'Простои'
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.line.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration(self):
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None

    def clean(self):
        if self.section and self.section.line != self.line:
            raise ValidationError({'section': 'Участок должен принадлежать выбранной линии'})
        
        if self.reason and self.reason.department != self.department:
            raise ValidationError({'reason': 'Причина должна принадлежать выбранному подразделению'})
        
        if self.end_time and self.start_time and self.end_time < self.start_time:
            raise ValidationError({'end_time': 'Время окончания не может быть раньше времени начала'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class DowntimeHistory(models.Model):
    downtime = models.ForeignKey(Downtime, on_delete=models.CASCADE, related_name='history', verbose_name='Простой')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Пользователь')
    action = models.CharField(max_length=50, verbose_name='Действие')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время действия')
    details = models.TextField(blank=True, verbose_name='Детали')

    class Meta:
        verbose_name = 'История простоя'
        verbose_name_plural = 'История простоев'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.downtime} - {self.action} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
