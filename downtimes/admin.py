from django.contrib import admin
from .models import Line, Section, Department, DowntimeReason, Downtime, DowntimeHistory, Shift
import datetime

class ShiftInline(admin.TabularInline):
    model = Shift
    extra = 1
    fields = ('name', 'start_time', 'end_time', 'is_active')
    show_change_link = True

@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'get_shifts_count')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    inlines = [ShiftInline]

    def get_shifts_count(self, obj):
        return obj.shifts.filter(is_active=True).count()
    get_shifts_count.short_description = 'Количество активных смен'

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'line', 'is_active')
    list_filter = ('is_active', 'line')
    search_fields = ('name', 'description', 'line__name')
    autocomplete_fields = ['line']  # Включаем автодополнение для линии
    list_select_related = ['line']  # Оптимизация запросов

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "line":
            kwargs["queryset"] = Line.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

@admin.register(DowntimeReason)
class DowntimeReasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'is_active')
    list_filter = ('is_active', 'department')
    search_fields = ('name', 'description', 'department__name')
    autocomplete_fields = ['department']
    list_select_related = ['department']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "department":
            kwargs["queryset"] = Department.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('name', 'line', 'start_time', 'end_time', 'is_active', 'get_duration')
    list_filter = ('is_active', 'line')
    search_fields = ('name', 'line__name')
    autocomplete_fields = ['line']
    list_select_related = ['line']
    readonly_fields = ('get_duration',)

    def get_duration(self, obj):
        if obj.start_time and obj.end_time:
            start_dt = datetime.datetime.combine(datetime.date.today(), obj.start_time)
            end_dt = datetime.datetime.combine(datetime.date.today(), obj.end_time)
            
            if obj.end_time < obj.start_time:
                end_dt += datetime.timedelta(days=1)
            
            duration = end_dt - start_dt
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            
            return f"{hours}ч {minutes}м"
        return "-"
    get_duration.short_description = 'Длительность'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "line":
            kwargs["queryset"] = Line.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(DowntimeHistory)
class DowntimeHistoryAdmin(admin.ModelAdmin):
    list_display = ('downtime', 'user', 'get_action', 'timestamp')
    list_filter = ('timestamp', 'user')
    search_fields = ('downtime__id', 'user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('downtime', 'user', 'timestamp', 'changes')
    ordering = ('-timestamp',)

    def get_action(self, obj):
        return obj.changes.get('action', '')
    get_action.short_description = 'Действие'

class DowntimeHistoryInline(admin.TabularInline):
    model = DowntimeHistory
    extra = 0
    readonly_fields = ('user', 'timestamp', 'changes')
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Downtime)
class DowntimeAdmin(admin.ModelAdmin):
    list_display = ('id', 'line', 'section', 'department', 'reason', 'start_time', 'end_time', 'created_by')
    list_filter = ('line', 'section', 'department', 'reason', 'start_time')
    search_fields = ('id', 'notes', 'created_by__username', 'created_by__first_name', 'created_by__last_name')
    readonly_fields = ('created_by',)
    inlines = [DowntimeHistoryInline]
