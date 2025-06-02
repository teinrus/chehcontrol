from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    full_name = models.CharField(max_length=255, verbose_name='Полное имя')

    ROLE_USER = 'user'
    ROLE_ENGINEER = 'engineer'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_USER, 'Пользователь'),
        (ROLE_ENGINEER, 'Инженер'),
        (ROLE_ADMIN, 'Администратор'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER, verbose_name='Роль')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    def get_full_name(self):
        return self.full_name or self.username

    def get_role_level(self):
        hierarchy = {
            self.ROLE_USER: 1,
            self.ROLE_ENGINEER: 2,
            self.ROLE_ADMIN: 3,
        }
        return hierarchy.get(self.role, 0)

    def has_role_at_least(self, required_role):
        hierarchy = {
            self.ROLE_USER: 1,
            self.ROLE_ENGINEER: 2,
            self.ROLE_ADMIN: 3,
        }
        return self.get_role_level() >= hierarchy.get(required_role, 0)
