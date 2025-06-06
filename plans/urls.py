from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("", views.lines_list, name="lines"),
    path("line/<int:line_id>/", views.plans_calendar, name="calendar"),
    path("create/", views.create_plan, name="create_plan"),
    path("get/<int:plan_id>/", views.get_plan, name="get_plan"),
    path("edit/<int:plan_id>/", views.edit_plan, name="edit_plan"),
]
