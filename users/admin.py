from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительно', {'fields': ('full_name', 'role')}),
    )
    list_display = ('username', 'full_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'full_name', 'email')
    ordering = ('username',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_role_at_least(CustomUser.ROLE_ADMIN):
            return qs.filter(id=request.user.id)
        return qs
