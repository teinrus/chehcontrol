from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from .models import CustomUser

def role_required(required_role):
    """
    Декоратор для проверки роли пользователя.
    required_role: минимальная требуемая роль (ROLE_OPERATOR, ROLE_ENGINEER, ROLE_ADMIN)
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Для доступа к этой странице необходимо войти в систему.')
                return redirect('login')
            
            if not request.user.has_role_at_least(required_role):
                messages.error(request, 'У вас нет прав для доступа к этой странице.')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator 