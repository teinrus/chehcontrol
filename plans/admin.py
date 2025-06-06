from django.contrib import admin

from .models import Plan, PlanItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    ordering = ("name",)


class PlanItemInline(admin.TabularInline):
    model = PlanItem
    extra = 1
    fields = (
        "product",
        "planned_quantity",
        "completed_quantity",
        "notes",
    )


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "line",
        "shift",
        "date",
        "status",
        "get_total_planned",
        "get_total_completed",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "line", "shift", "date")
    search_fields = ("line__name", "shift__name", "notes")
    date_hierarchy = "date"
    inlines = [PlanItemInline]
    readonly_fields = ("created_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not change:  # Если это создание нового объекта
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PlanItem)
class PlanItemAdmin(admin.ModelAdmin):
    list_display = (
        "plan",
        "product",
        "planned_quantity",
        "completed_quantity",
        "get_completion_percentage",
    )
    list_filter = ("plan__line", "plan__shift", "plan__date", "product")
    search_fields = ("product__name", "notes", "plan__line__name")
    readonly_fields = ("get_completion_percentage",)
