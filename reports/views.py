from django.shortcuts import render
from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .forms import ReportFilterForm
from downtimes.models import Downtime, Line, Shift
from django.utils import timezone
from datetime import datetime, timedelta, time
from django.db.models import Q

# Create your views here.

class ReportFilterView(LoginRequiredMixin, FormView):
    template_name = 'reports/report_filter.html'
    form_class = ReportFilterForm
    success_url = reverse_lazy('reports:report_results')

    def form_valid(self, form):
        # Сохраняем выбранные параметры в сессии
        self.request.session['report_line'] = form.cleaned_data['line'].id
        self.request.session['report_date'] = form.cleaned_data['date'].strftime('%Y-%m-%d')
        if form.cleaned_data['shift']:
            self.request.session['report_shift'] = form.cleaned_data['shift'].id
        else:
            self.request.session['report_shift'] = None
        return super().form_valid(form)

class ReportResultsView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/report_results.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Получаем параметры из сессии
        line_id = self.request.session.get('report_line')
        date_str = self.request.session.get('report_date')
        shift_id = self.request.session.get('report_shift')
        
        if not all([line_id, date_str]):
            context['error'] = 'Не выбраны параметры отчета'
            return context
        
        try:
            line = Line.objects.get(id=line_id)
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Получаем простои для выбранных параметров
            qs = Downtime.objects.filter(line=line)
            
            # Фильтруем по дате
            qs = qs.filter(
                start_time__gte=timezone.make_aware(datetime.combine(selected_date, time.min)),
                start_time__lt=timezone.make_aware(datetime.combine(selected_date + timedelta(days=1), time.min))
            )
            
            # Если выбрана конкретная смена, фильтруем по ней
            if shift_id:
                try:
                    shift = Shift.objects.get(id=shift_id)
                    if shift.start_time > shift.end_time:
                        # Смена переходит через полночь
                        qs = qs.filter(
                            (Q(start_time__gte=timezone.make_aware(datetime.combine(selected_date, shift.start_time))) &
                             Q(start_time__lt=timezone.make_aware(datetime.combine(selected_date + timedelta(days=1), time.min)))) |
                            (Q(start_time__gte=timezone.make_aware(datetime.combine(selected_date, time.min))) &
                             Q(start_time__lt=timezone.make_aware(datetime.combine(selected_date, shift.end_time))))
                        )
                    else:
                        # Обычная смена
                        qs = qs.filter(
                            start_time__gte=timezone.make_aware(datetime.combine(selected_date, shift.start_time)),
                            start_time__lt=timezone.make_aware(datetime.combine(selected_date, shift.end_time))
                        )
                    context['shift'] = shift
                except Shift.DoesNotExist:
                    pass
            
            # Добавляем данные в контекст
            context['line'] = line
            context['date'] = selected_date
            context['downtimes'] = qs.order_by('start_time')
            
            # Считаем общую длительность простоев
            total_duration = timedelta()
            for downtime in qs:
                if downtime.end_time:
                    duration = downtime.end_time - downtime.start_time
                    total_duration += duration
            
            context['total_duration'] = total_duration
            
        except Line.DoesNotExist:
            context['error'] = 'Выбранная линия не существует'
        
        return context
