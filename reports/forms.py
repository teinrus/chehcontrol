from django import forms
from downtimes.models import Line, Shift
from django.utils import timezone

class ReportFilterForm(forms.Form):
    line = forms.ModelChoiceField(
        queryset=Line.objects.filter(is_active=True),
        label='Линия',
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_line'
        })
    )
    
    date = forms.DateField(
        label='Дата',
        required=True,
        initial=timezone.now,
        input_formats=['%Y-%m-%d'],  # Добавляем правильный формат
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'id_date',
            'format': 'yyyy-MM-dd'  # Добавляем формат для input
        })
    )
    
    shift = forms.ModelChoiceField(
        queryset=Shift.objects.filter(is_active=True).order_by('line', 'start_time'),
        label='Смена',
        required=False,  # Делаем поле необязательным
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_shift'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем классы Bootstrap для стилизации
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
        
        # Добавляем пустую опцию для смен
        self.fields['shift'].empty_label = 'Все сутки'
        
        # Если форма уже заполнена, фильтруем смены по выбранной линии
        if 'line' in self.data:
            try:
                line_id = int(self.data.get('line'))
                self.fields['shift'].queryset = Shift.objects.filter(
                    line_id=line_id,
                    is_active=True
                ).order_by('start_time')
            except (ValueError, TypeError):
                pass 