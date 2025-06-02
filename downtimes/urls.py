from django.urls import path
from . import views

app_name = 'downtimes'

urlpatterns = [
    path('', views.DowntimeListView.as_view(), name='downtime_list'),
    path('create/', views.DowntimeCreateView.as_view(), name='downtime_create'),
    path('<int:pk>/', views.DowntimeDetailView.as_view(), name='downtime_detail'),
    path('<int:pk>/update/', views.DowntimeUpdateView.as_view(), name='downtime_update'),
    path('<int:pk>/delete/', views.DowntimeDeleteView.as_view(), name='downtime_delete'),
    
    # URL для линий
    path('lines/', views.LineListView.as_view(), name='line_list'),
    path('lines/create/', views.LineCreateView.as_view(), name='line_create'),
    path('lines/<int:pk>/', views.LineDetailView.as_view(), name='line_detail'),
    path('lines/<int:pk>/update/', views.LineUpdateView.as_view(), name='line_update'),
    path('lines/<int:pk>/delete/', views.LineDeleteView.as_view(), name='line_delete'),

    # URL-маршруты для подразделений
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/update/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/delete/', views.DepartmentDeleteView.as_view(), name='department_delete'),

    # URL-маршруты для участков
    path('sections/', views.SectionListView.as_view(), name='section_list'),
    path('sections/create/', views.SectionCreateView.as_view(), name='section_create'),
    path('sections/<int:pk>/update/', views.SectionUpdateView.as_view(), name='section_update'),
    path('sections/<int:pk>/delete/', views.SectionDeleteView.as_view(), name='section_delete'),

    # URL-маршруты для причин простоев
    path('reasons/', views.DowntimeReasonListView.as_view(), name='reason_list'),
    path('reasons/create/', views.DowntimeReasonCreateView.as_view(), name='reason_create'),
    path('reasons/<int:pk>/update/', views.DowntimeReasonUpdateView.as_view(), name='reason_update'),
    path('reasons/<int:pk>/delete/', views.DowntimeReasonDeleteView.as_view(), name='reason_delete'),

    path('api/sections/', views.get_sections, name='api_sections'),
    path('api/reasons/', views.get_reasons, name='api_reasons'),

    # URLs для смен
    path('shifts/', views.ShiftListView.as_view(), name='shift_list'),
    path('shifts/create/', views.ShiftCreateView.as_view(), name='shift_create'),
    path('shifts/<int:pk>/update/', views.ShiftUpdateView.as_view(), name='shift_update'),
    path('shifts/<int:pk>/delete/', views.ShiftDeleteView.as_view(), name='shift_delete'),
] 