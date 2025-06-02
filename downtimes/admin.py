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

class DowntimeHistoryInline(admin.TabularInline):
    model = DowntimeHistory
    extra = 0
    readonly_fields = ('user', 'action', 'timestamp', 'get_details')
    can_delete = False
    ordering = ['-timestamp']

    def has_add_permission(self, request, obj=None):
        return False

    def get_details(self, obj):
        if obj.action == 'Создан':
            return f"Создан новый простой пользователем {obj.user.username}"
        elif obj.action == 'Изменен':
            details = obj.details.split('\n')
            formatted_details = []
            for detail in details:
                if ':' in detail:
                    field, values = detail.split(':', 1)
                    old_value, new_value = values.split('→')
                    formatted_details.append(f"{field.strip()}: {old_value.strip()} → {new_value.strip()}")
            return '\n'.join(formatted_details)
        return obj.details
    get_details.short_description = 'Детали'

@admin.register(Downtime)
class DowntimeAdmin(admin.ModelAdmin):
    list_display = ('line', 'section', 'department', 'start_time', 'end_time', 'is_active', 'get_duration')
    list_filter = ('is_active', 'line', 'department', 'start_time')
    search_fields = ('notes', 'line__name', 'section__name', 'department__name')
    autocomplete_fields = ['line', 'section', 'department', 'reason', 'created_by']
    readonly_fields = ('get_duration',)
    inlines = [DowntimeHistoryInline]
    fieldsets = (
        ('Основная информация', {
            'fields': ('line', 'section', 'is_active')
        }),
        ('Время простоя', {
            'fields': ('start_time', 'end_time', 'get_duration')
        }),
        ('Причина простоя', {
            'fields': ('department', 'reason')
        }),
        ('Дополнительно', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    def get_duration(self, obj):
        if obj.end_time and obj.start_time:
            duration = obj.end_time - obj.start_time
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            return f"{hours}ч {minutes}м"
        return "-"
    get_duration.short_description = 'Длительность'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "department":
            kwargs["queryset"] = Department.objects.filter(is_active=True)
        elif db_field.name == "reason":
            kwargs["queryset"] = DowntimeReason.objects.filter(is_active=True)
        elif db_field.name == "line":
            kwargs["queryset"] = Line.objects.filter(is_active=True)
        elif db_field.name == "section":
            kwargs["queryset"] = Section.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:  # Если это новая запись
            obj.created_by = request.user
            action = 'Создан'
            details = f"Создан новый простой пользователем {request.user.username}"
        else:
            action = 'Изменен'
            changed_fields = []
            for field in form.changed_data:
                if field not in ['updated_at']:  # Исключаем служебные поля
                    old_value = form.initial.get(field, '')
                    new_value = form.cleaned_data.get(field, '')
                    if field == 'line':
                        old_value = Line.objects.get(id=old_value).name if old_value else ''
                        new_value = new_value.name if new_value else ''
                    elif field == 'section':
                        old_value = Section.objects.get(id=old_value).name if old_value else ''
                        new_value = new_value.name if new_value else ''
                    elif field == 'department':
                        old_value = Department.objects.get(id=old_value).name if old_value else ''
                        new_value = new_value.name if new_value else ''
                    elif field == 'reason':
                        old_value = DowntimeReason.objects.get(id=old_value).name if old_value else ''
                        new_value = new_value.name if new_value else ''
                    changed_fields.append(f"{field}: {old_value} → {new_value}")
            details = "Изменения:\n" + "\n".join(changed_fields)
        
        super().save_model(request, obj, form, change)
        
        # Создаем запись в истории
        DowntimeHistory.objects.create(
            downtime=obj,
            user=request.user,
            action=action,
            details=details
        )

@admin.register(DowntimeHistory)
class DowntimeHistoryAdmin(admin.ModelAdmin):
    list_display = ('downtime', 'user', 'action', 'timestamp', 'get_details')
    list_filter = ('action', 'timestamp', 'user')
    search_fields = ('downtime__line__name', 'user__username', 'details')
    readonly_fields = ('downtime', 'user', 'action', 'timestamp', 'get_details')
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    def has_add_permission(self, request):
        return False

    def get_details(self, obj):
        if obj.action == 'Создан':
            return f"Создан новый простой пользователем {obj.user.username}"
        elif obj.action == 'Изменен':
            details = obj.details.split('\n')
            formatted_details = []
            for detail in details:
                if ':' in detail:
                    field, values = detail.split(':', 1)
                    old_value, new_value = values.split('→')
                    formatted_details.append(f"{field.strip()}: {old_value.strip()} → {new_value.strip()}")
            return '\n'.join(formatted_details)
        return obj.details
    get_details.short_description = 'Детали'
