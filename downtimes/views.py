from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Downtime, Line, Department, Section, DowntimeReason, Shift
from users.decorators import role_required
from users.models import CustomUser
from django.utils.decorators import method_decorator
from django.forms import DateTimeInput, TimeInput
from django.utils import timezone
from datetime import datetime, timedelta, time
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Q

# Create your views here.

class DowntimeListView(LoginRequiredMixin, ListView):
    model = Downtime
    template_name = 'downtimes/downtime_list.html'
    context_object_name = 'downtimes'
    ordering = ['-start_time']

    def get_queryset(self):
        line_id = self.request.GET.get('line')
        date_str = self.request.GET.get('date')
        shift_id = self.request.GET.get('shift')
        
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                selected_date = timezone.now().date()
        else:
            selected_date = timezone.now().date()

        qs = Downtime.objects.all()
        if line_id:
            qs = qs.filter(line_id=line_id)
            # Проверяем, есть ли смены у выбранной линии
            line_has_shifts = Shift.objects.filter(line_id=line_id, is_active=True).exists()
        else:
            line_has_shifts = False
        
        # Фильтрация по дате и смене
        if shift_id and line_has_shifts:
            try:
                shift = Shift.objects.get(id=shift_id)
                # Если смена переходит через полночь
                if shift.start_time > shift.end_time:
                    # Для смены, переходящей через полночь, проверяем два периода
                    qs = qs.filter(
                        (Q(start_time__gte=timezone.make_aware(datetime.combine(selected_date, shift.start_time))) &
                         Q(start_time__lt=timezone.make_aware(datetime.combine(selected_date + timedelta(days=1), time.min)))) |
                        (Q(start_time__gte=timezone.make_aware(datetime.combine(selected_date, time.min))) &
                         Q(start_time__lt=timezone.make_aware(datetime.combine(selected_date, shift.end_time))))
                    )
                else:
                    # Для обычной смены
                    qs = qs.filter(
                        start_time__gte=timezone.make_aware(datetime.combine(selected_date, shift.start_time)),
                        start_time__lt=timezone.make_aware(datetime.combine(selected_date, shift.end_time))
                    )
            except Shift.DoesNotExist:
                pass
        else:
            # Если смена не выбрана или у линии нет смен, фильтруем по дате
            qs = qs.filter(
                start_time__gte=timezone.make_aware(datetime.combine(selected_date, time.min)),
                start_time__lt=timezone.make_aware(datetime.combine(selected_date + timedelta(days=1), time.min))
            )
        
        return qs.order_by('-start_time')

    def get_current_shift(self, line, current_datetime):
        """Определяет текущую смену для линии на основе текущего времени."""
        shifts = Shift.objects.filter(line=line, is_active=True)
        
        for shift in shifts:
            # Создаем datetime объекты для начала и конца смены
            shift_start_dt = datetime.combine(current_datetime.date(), shift.start_time)
            shift_end_dt = datetime.combine(current_datetime.date(), shift.end_time)
            
            # Делаем datetime объекты aware (с часовым поясом)
            shift_start_dt = timezone.make_aware(shift_start_dt)
            shift_end_dt = timezone.make_aware(shift_end_dt)
            
            if shift.start_time > shift.end_time:
                # Смена переходит через полночь
                shift_end_dt += timedelta(days=1)
                if shift_start_dt <= current_datetime < shift_end_dt:
                    return shift
            else:
                # Обычная смена
                if shift_start_dt <= current_datetime < shift_end_dt:
                    return shift
        return None

    def get_shift_for_downtime(self, downtime, shift, selected_date):
        """Определяет, принадлежит ли простой к указанной смене."""
        # Создаем datetime объекты для начала и конца смены
        shift_start_dt = datetime.combine(selected_date, shift.start_time)
        shift_end_dt = datetime.combine(selected_date, shift.end_time)
        
        # Делаем datetime объекты aware
        shift_start_dt = timezone.make_aware(shift_start_dt)
        shift_end_dt = timezone.make_aware(shift_end_dt)
        
        # Получаем время начала простоя
        downtime_start = downtime.start_time
        
        if shift.start_time > shift.end_time:
            # Смена переходит через полночь
            shift_end_dt += timedelta(days=1)
            return shift_start_dt <= downtime_start < shift_end_dt
        else:
            # Обычная смена
            return shift_start_dt <= downtime_start < shift_end_dt

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lines'] = Line.objects.all()
        context['selected_line'] = self.request.GET.get('line')
        
        # Получаем выбранную дату или используем текущую
        date_str = self.request.GET.get('date')
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                selected_date = timezone.now().date()
        else:
            selected_date = timezone.now().date()
        context['selected_date'] = selected_date.strftime('%Y-%m-%d')
        
        context['selected_shift'] = self.request.GET.get('shift')
        
        # Получаем смены для выбранной линии
        if context['selected_line']:
            context['shifts'] = Shift.objects.filter(
                line_id=context['selected_line'],
                is_active=True
            ).order_by('start_time')
        else:
            context['shifts'] = Shift.objects.filter(is_active=True).order_by('start_time')
        
        # Получаем все активные смены для всех линий
        active_shifts = Shift.objects.filter(is_active=True)
        line_shifts = {}
        for shift in active_shifts:
            if shift.line_id not in line_shifts:
                line_shifts[shift.line_id] = []
            line_shifts[shift.line_id].append(shift)
        
        # Определяем текущее время с учетом часового пояса
        current_datetime = timezone.localtime(timezone.now())
        
        # Группируем простои по линиям
        downtimes_by_line = {}
        for line in context['lines']:
            line_downtimes = [d for d in context['downtimes'] if d.line == line]
            if line_downtimes:  # Добавляем только если есть простои
                # Определяем текущую смену для линии
                current_shift = self.get_current_shift(line, current_datetime)
                
                # Группируем простои по сменам
                downtimes_by_shift = {}
                
                # Если есть текущая смена, добавляем только её простои
                if current_shift:
                    shift_downtimes = []
                    for downtime in line_downtimes:
                        if self.get_shift_for_downtime(downtime, current_shift, selected_date):
                            shift_downtimes.append(downtime)
                    
                    if shift_downtimes:
                        # Сортируем простои по времени начала
                        shift_downtimes.sort(key=lambda x: x.start_time)
                        downtimes_by_shift[current_shift] = shift_downtimes
                
                downtimes_by_line[line] = {
                    'downtimes_by_shift': downtimes_by_shift,
                    'has_shifts': line.id in line_shifts,
                    'current_shift': current_shift,
                    'debug_info': {
                        'current_datetime': current_datetime,
                        'selected_date': selected_date,
                        'shifts': line_shifts.get(line.id, [])
                    }
                }
        context['downtimes_by_line'] = downtimes_by_line
        
        return context

class DowntimeDetailView(LoginRequiredMixin, DetailView):
    model = Downtime
    template_name = 'downtimes/downtime_detail.html'
    context_object_name = 'downtime'

    def dispatch(self, request, *args, **kwargs):
        # Получаем объект простоя
        self.object = self.get_object()
        
        # Проверяем права доступа
        if request.user.role == CustomUser.ROLE_USER:
            # Пользователь может просматривать только свои простои
            if self.object.created_by != request.user:
                messages.error(request, 'У вас нет прав для просмотра этого простоя')
                return self.handle_no_permission()
        elif request.user.role not in [CustomUser.ROLE_ENGINEER, CustomUser.ROLE_ADMIN]:
            messages.error(request, 'У вас нет прав для просмотра простоев')
            return self.handle_no_permission()
            
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['history'] = self.object.history.all()
        return context

class DowntimeCreateView(LoginRequiredMixin, CreateView):
    model = Downtime
    template_name = 'downtimes/downtime_form.html'
    fields = ['line', 'section', 'department', 'reason', 'start_time', 'end_time', 'notes']
    success_url = reverse_lazy('downtimes:downtime_list')

    def dispatch(self, request, *args, **kwargs):
        # Проверяем права доступа
        if request.user.role not in [CustomUser.ROLE_USER, CustomUser.ROLE_ENGINEER, CustomUser.ROLE_ADMIN]:
            messages.error(request, 'У вас нет прав для создания простоев')
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        now = timezone.now()
        
        # Устанавливаем начальные значения для полей времени
        form.fields['start_time'].initial = now
        form.fields['end_time'].initial = now + timedelta(minutes=5)
        
        # Настраиваем виджеты для полей времени
        form.fields['start_time'].widget = DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'min': now.strftime('%Y-%m-%dT%H:%M')
            }
        )
        form.fields['end_time'].widget = DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'min': now.strftime('%Y-%m-%dT%H:%M')
            }
        )
        
        # Фильтруем линии по активным
        form.fields['line'].queryset = Line.objects.filter(is_active=True)
        
        # Ограничиваем участки по выбранной линии
        line_id = self.request.POST.get('line')
        if line_id:
            form.fields['section'].queryset = Section.objects.filter(line_id=line_id, is_active=True)
        else:
            form.fields['section'].queryset = Section.objects.none()
        
        # Ограничиваем причины по выбранному подразделению
        department_id = self.request.POST.get('department')
        if department_id:
            form.fields['reason'].queryset = DowntimeReason.objects.filter(department_id=department_id, is_active=True)
        else:
            form.fields['reason'].queryset = DowntimeReason.objects.none()
        
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Простой успешно создан')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме.')
        return super().form_invalid(form)

class DowntimeUpdateView(LoginRequiredMixin, UpdateView):
    model = Downtime
    template_name = 'downtimes/downtime_form.html'
    fields = ['line', 'section', 'department', 'reason', 'start_time', 'end_time', 'notes']
    success_url = reverse_lazy('downtimes:downtime_list')

    def dispatch(self, request, *args, **kwargs):
        # Проверяем права доступа
        if request.user.role not in [CustomUser.ROLE_USER, CustomUser.ROLE_ENGINEER, CustomUser.ROLE_ADMIN]:
            messages.error(request, 'У вас нет прав для редактирования простоев')
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        instance = self.get_object()
        
        # Фильтруем линии по активным
        form.fields['line'].queryset = Line.objects.filter(is_active=True)
        
        # Ограничиваем участки по выбранной линии
        line_id = self.request.POST.get('line') or getattr(instance.line, 'id', None)
        if line_id:
            form.fields['section'].queryset = Section.objects.filter(line_id=line_id, is_active=True)
            # Устанавливаем начальное значение участка
            form.initial['section'] = instance.section
        else:
            form.fields['section'].queryset = Section.objects.none()
        
        # Ограничиваем причины по выбранному подразделению
        department_id = self.request.POST.get('department') or getattr(instance.department, 'id', None)
        if department_id:
            form.fields['reason'].queryset = DowntimeReason.objects.filter(department_id=department_id, is_active=True)
            # Устанавливаем начальное значение причины
            form.initial['reason'] = instance.reason
        else:
            form.fields['reason'].queryset = DowntimeReason.objects.none()
        
        # Устанавливаем начальные значения для полей времени
        if instance.start_time:
            # Преобразуем время в локальный часовой пояс
            local_start_time = timezone.localtime(instance.start_time)
            form.initial['start_time'] = local_start_time.strftime('%Y-%m-%dT%H:%M')
        else:
            now = timezone.now()
            form.initial['start_time'] = now.strftime('%Y-%m-%dT%H:%M')
            
        if instance.end_time:
            # Преобразуем время в локальный часовой пояс
            local_end_time = timezone.localtime(instance.end_time)
            form.initial['end_time'] = local_end_time.strftime('%Y-%m-%dT%H:%M')
        else:
            form.initial['end_time'] = None

        # Настраиваем виджеты для полей времени
        form.fields['start_time'].widget = DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }
        )
        form.fields['end_time'].widget = DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }
        )
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Простой успешно обновлен')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме.')
        return super().form_invalid(form)

class DowntimeDeleteView(LoginRequiredMixin, DeleteView):
    model = Downtime
    template_name = 'downtimes/downtime_confirm_delete.html'
    success_url = reverse_lazy('downtimes:downtime_list')

    def dispatch(self, request, *args, **kwargs):
        # Получаем объект простоя
        self.object = self.get_object()
        
        # Проверяем права доступа
        if request.user.role == CustomUser.ROLE_USER:
            # Пользователь может удалять только свои простои
            if self.object.created_by != request.user:
                messages.error(request, 'У вас нет прав для удаления этого простоя')
                return self.handle_no_permission()
        elif request.user.role not in [CustomUser.ROLE_ENGINEER, CustomUser.ROLE_ADMIN]:
            messages.error(request, 'У вас нет прав для удаления простоев')
            return self.handle_no_permission()
            
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Простой успешно удален')
        return super().delete(request, *args, **kwargs)

class LineListView(LoginRequiredMixin, ListView):
    model = Line
    template_name = 'downtimes/line_list.html'
    context_object_name = 'lines'
    ordering = ['name']

    def get_queryset(self):
        return Line.objects.all()

class LineDetailView(LoginRequiredMixin, DetailView):
    model = Line
    template_name = 'downtimes/line_detail.html'
    context_object_name = 'line'

class LineCreateView(LoginRequiredMixin, CreateView):
    model = Line
    template_name = 'downtimes/line_form.html'
    fields = ['name', 'description', 'is_active']
    success_url = reverse_lazy('downtimes:line_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.role in [CustomUser.ROLE_ENGINEER, CustomUser.ROLE_ADMIN]:
            messages.error(request, 'У вас нет прав для создания линий')
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Линия успешно создана')
        return super().form_valid(form)

class LineUpdateView(LoginRequiredMixin, UpdateView):
    model = Line
    template_name = 'downtimes/line_form.html'
    fields = ['name', 'description', 'is_active']
    success_url = reverse_lazy('downtimes:line_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.role in [CustomUser.ROLE_ENGINEER, CustomUser.ROLE_ADMIN]:
            messages.error(request, 'У вас нет прав для редактирования линий')
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Линия успешно обновлена')
        return super().form_valid(form)

class LineDeleteView(LoginRequiredMixin, DeleteView):
    model = Line
    template_name = 'downtimes/line_confirm_delete.html'
    success_url = reverse_lazy('downtimes:line_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.role in [CustomUser.ROLE_ENGINEER, CustomUser.ROLE_ADMIN]:
            messages.error(request, 'У вас нет прав для удаления линий')
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Линия успешно удалена')
        return super().delete(request, *args, **kwargs)

# Представления для подразделений
class DepartmentListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = 'downtimes/department_list.html'
    context_object_name = 'departments'
    ordering = ['name']

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    template_name = 'downtimes/department_form.html'
    fields = ['name', 'description', 'is_active']
    success_url = reverse_lazy('downtimes:department_list')

    def form_valid(self, form):
        messages.success(self.request, 'Подразделение успешно создано')
        return super().form_valid(form)

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Department
    template_name = 'downtimes/department_form.html'
    fields = ['name', 'description', 'is_active']
    success_url = reverse_lazy('downtimes:department_list')

    def form_valid(self, form):
        messages.success(self.request, 'Подразделение успешно обновлено')
        return super().form_valid(form)

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class DepartmentDeleteView(LoginRequiredMixin, DeleteView):
    model = Department
    template_name = 'downtimes/department_confirm_delete.html'
    success_url = reverse_lazy('downtimes:department_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Подразделение успешно удалено')
        return super().delete(request, *args, **kwargs)

# Представления для участков
class SectionListView(LoginRequiredMixin, ListView):
    model = Section
    template_name = 'downtimes/section_list.html'
    context_object_name = 'sections'
    ordering = ['name']

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class SectionCreateView(LoginRequiredMixin, CreateView):
    model = Section
    template_name = 'downtimes/section_form.html'
    fields = ['name', 'line', 'description', 'is_active']
    success_url = reverse_lazy('downtimes:section_list')

    def form_valid(self, form):
        messages.success(self.request, 'Участок успешно создан')
        return super().form_valid(form)

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class SectionUpdateView(LoginRequiredMixin, UpdateView):
    model = Section
    template_name = 'downtimes/section_form.html'
    fields = ['name', 'line', 'description', 'is_active']
    success_url = reverse_lazy('downtimes:section_list')

    def form_valid(self, form):
        messages.success(self.request, 'Участок успешно обновлен')
        return super().form_valid(form)

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class SectionDeleteView(LoginRequiredMixin, DeleteView):
    model = Section
    template_name = 'downtimes/section_confirm_delete.html'
    success_url = reverse_lazy('downtimes:section_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Участок успешно удален')
        return super().delete(request, *args, **kwargs)

# Представления для причин простоев
class DowntimeReasonListView(LoginRequiredMixin, ListView):
    model = DowntimeReason
    template_name = 'downtimes/reason_list.html'
    context_object_name = 'reasons'
    ordering = ['name']

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class DowntimeReasonCreateView(LoginRequiredMixin, CreateView):
    model = DowntimeReason
    template_name = 'downtimes/reason_form.html'
    fields = ['name', 'department', 'description', 'is_active']
    success_url = reverse_lazy('downtimes:reason_list')

    def form_valid(self, form):
        messages.success(self.request, 'Причина простоя успешно создана')
        return super().form_valid(form)

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class DowntimeReasonUpdateView(LoginRequiredMixin, UpdateView):
    model = DowntimeReason
    template_name = 'downtimes/reason_form.html'
    fields = ['name', 'department', 'description', 'is_active']
    success_url = reverse_lazy('downtimes:reason_list')

    def form_valid(self, form):
        messages.success(self.request, 'Причина простоя успешно обновлена')
        return super().form_valid(form)

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class DowntimeReasonDeleteView(LoginRequiredMixin, DeleteView):
    model = DowntimeReason
    template_name = 'downtimes/reason_confirm_delete.html'
    success_url = reverse_lazy('downtimes:reason_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Причина простоя успешно удалена')
        return super().delete(request, *args, **kwargs)

@login_required
@require_http_methods(["GET"])
def get_sections(request):
    line_id = request.GET.get('line')
    if not line_id:
        return JsonResponse([], safe=False)
    
    sections = Section.objects.filter(line_id=line_id, is_active=True)
    data = [{'id': section.id, 'name': section.name} for section in sections]
    return JsonResponse(data, safe=False)

@login_required
@require_http_methods(["GET"])
def get_reasons(request):
    department_id = request.GET.get('department')
    if not department_id:
        return JsonResponse([], safe=False)
    
    reasons = DowntimeReason.objects.filter(department_id=department_id, is_active=True)
    data = [{'id': reason.id, 'name': reason.name} for reason in reasons]
    return JsonResponse(data, safe=False)

# Представления для смен
class ShiftListView(LoginRequiredMixin, ListView):
    model = Shift
    template_name = 'downtimes/shift_list.html'
    context_object_name = 'shifts'
    ordering = ['line', 'start_time']

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class ShiftCreateView(LoginRequiredMixin, CreateView):
    model = Shift
    template_name = 'downtimes/shift_form.html'
    fields = ['name', 'line', 'start_time', 'end_time', 'is_active']
    success_url = reverse_lazy('downtimes:shift_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['line'].queryset = Line.objects.filter(is_active=True)
        form.fields['start_time'].widget = TimeInput(attrs={'type': 'time', 'class': 'form-control'})
        form.fields['end_time'].widget = TimeInput(attrs={'type': 'time', 'class': 'form-control'})
        return form

    def form_valid(self, form):
        messages.success(self.request, 'Смена успешно создана')
        return super().form_valid(form)

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class ShiftUpdateView(LoginRequiredMixin, UpdateView):
    model = Shift
    template_name = 'downtimes/shift_form.html'
    fields = ['name', 'line', 'start_time', 'end_time', 'is_active']
    success_url = reverse_lazy('downtimes:shift_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['line'].queryset = Line.objects.filter(is_active=True)
        form.fields['start_time'].widget = TimeInput(attrs={'type': 'time', 'class': 'form-control'})
        form.fields['end_time'].widget = TimeInput(attrs={'type': 'time', 'class': 'form-control'})
        return form

    def form_valid(self, form):
        messages.success(self.request, 'Смена успешно обновлена')
        return super().form_valid(form)

@method_decorator(role_required(CustomUser.ROLE_ENGINEER), name='dispatch')
class ShiftDeleteView(LoginRequiredMixin, DeleteView):
    model = Shift
    template_name = 'downtimes/shift_confirm_delete.html'
    success_url = reverse_lazy('downtimes:shift_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Смена успешно удалена')
        return super().delete(request, *args, **kwargs)
