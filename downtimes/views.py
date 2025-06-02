from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Downtime, Line, Department, Section, DowntimeReason
from users.decorators import role_required
from users.models import CustomUser
from django.utils.decorators import method_decorator
from django.forms import DateTimeInput
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

# Create your views here.

class DowntimeListView(LoginRequiredMixin, ListView):
    model = Downtime
    template_name = 'downtimes/downtime_list.html'
    context_object_name = 'downtimes'
    ordering = ['-start_time']

    def get_queryset(self):
        # Показываем все простои для всех пользователей
        return Downtime.objects.all().order_by('-start_time')

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
