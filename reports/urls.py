from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.ReportFilterView.as_view(), name='report_filter'),
    path('results/', views.ReportResultsView.as_view(), name='report_results'),
] 