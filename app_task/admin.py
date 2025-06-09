from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at", "started_at", "completed_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "description", "result", "error_message")
    readonly_fields = ("created_at", "started_at", "completed_at")
