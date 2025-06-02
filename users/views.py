from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse_lazy
from django.contrib import messages
from .models import CustomUser
from .decorators import role_required

# Create your views here.

class CustomLoginView(LoginView):
    template_name = 'users/login.html'
    redirect_authenticated_user = True

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'users/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context

class UserListView(LoginRequiredMixin, ListView):
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    ordering = ['-date_joined']

    def get_queryset(self):
        return CustomUser.objects.all()

class UserCreateView(LoginRequiredMixin, CreateView):
    model = CustomUser
    template_name = 'users/user_form.html'
    fields = ['username', 'email', 'full_name', 'role', 'is_active', 'password']
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.save()
        
        messages.success(self.request, 'Пользователь успешно создан')
        return super().form_valid(form)

class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    template_name = 'users/user_form.html'
    fields = ['username', 'email', 'full_name', 'role', 'is_active']
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        messages.success(self.request, 'Пользователь успешно обновлен')
        return super().form_valid(form)

class UserDeleteView(LoginRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Пользователь успешно удален')
        return super().delete(request, *args, **kwargs)
