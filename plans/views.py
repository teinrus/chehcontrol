import calendar
import logging
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from downtimes.models import Line, Shift

from .models import Plan, PlanItem, Product

logger = logging.getLogger(__name__)

# Create your views here.


@login_required
def lines_list(request):
    """Отображение списка производственных линий."""
    lines = Line.objects.all()
    return render(request, "plans/lines.html", {"lines": lines})


@login_required
def plans_calendar(request, line_id):
    """Отображение календаря планов для линии."""
    try:
        line = Line.objects.get(id=line_id)
    except Line.DoesNotExist:
        return redirect("plans:calendar_list")

    # Получаем текущую дату в локальном времени
    today = timezone.localtime(timezone.now()).date()

    # Получаем год и месяц из параметров запроса или используем текущие
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except (ValueError, TypeError):
        year = today.year
        month = today.month

    # Создаем календарь
    cal = calendar.monthcalendar(year, month)

    # Получаем планы для выбранного месяца
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    plans = (
        Plan.objects.filter(line=line, date__gte=start_date, date__lt=end_date)
        .select_related("shift")
        .prefetch_related("items__product")
    )

    # Группируем планы по датам
    plans_by_date = {}
    for plan in plans:
        date_key = f"{plan.date.year:04d}-{plan.date.month:02d}-{plan.date.day:02d}"
        if date_key not in plans_by_date:
            plans_by_date[date_key] = []
        plans_by_date[date_key].append(plan)

    # Получаем предыдущий и следующий месяцы
    if month == 1:
        prev_month = date(year - 1, 12, 1)
        next_month = date(year, 2, 1)
    elif month == 12:
        prev_month = date(year, 11, 1)
        next_month = date(year + 1, 1, 1)
    else:
        prev_month = date(year, month - 1, 1)
        next_month = date(year, month + 1, 1)

    # Получаем все активные смены для этой линии
    shifts = Shift.objects.filter(line=line, is_active=True).order_by("name")

    # Проверяем наличие смен
    has_shifts = shifts.exists()
    if not has_shifts:
        messages.warning(
            request,
            "Для этой линии не настроены смены. Пожалуйста, добавьте смены перед созданием планов.",
        )

    context = {
        "line": line,
        "calendar": cal,
        "year": year,
        "month": month,
        "today": today,
        "plans_by_date": plans_by_date,
        "prev_month": prev_month,
        "next_month": next_month,
        "shifts": shifts,
        "has_shifts": has_shifts,
        "products": Product.objects.filter(is_active=True),
        "status_choices": Plan.STATUS_CHOICES,
    }

    return render(request, "plans/calendar.html", context)


@login_required
def create_plan(request):
    if request.method == "POST":
        try:
            # Получаем данные из формы
            line_id = request.POST.get("line")
            date_str = request.POST.get("date")
            shift_id = request.POST.get("shift")
            status = request.POST.get("status")
            products = request.POST.getlist("products[]")
            quantities = request.POST.getlist("quantities[]")
            completed_quantities = request.POST.getlist("completed_quantities[]")

            # Проверяем наличие всех необходимых данных
            if not all([line_id, date_str, shift_id, status, products, quantities]):
                return JsonResponse(
                    {"status": "error", "message": "Не все данные предоставлены"}
                )

            # Преобразуем строку даты в объект date
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse(
                    {"status": "error", "message": "Неверный формат даты"}
                )

            # Получаем объекты линии и смены
            line = Line.objects.get(id=line_id)
            shift = Shift.objects.get(id=shift_id)

            # Проверяем, что смена принадлежит выбранной линии
            if shift.line != line:
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "Смена должна принадлежать выбранной линии",
                    }
                )

            # Проверяем существование плана
            existing_plan = Plan.objects.filter(
                line=line, shift=shift, date=date
            ).first()

            if existing_plan:
                # Обновляем существующий план
                existing_plan.status = status
                existing_plan.save()

                # Удаляем старые позиции плана
                existing_plan.items.all().delete()

                # Создаем новые позиции плана
                for product_id, quantity, completed_quantity in zip(
                    products, quantities, completed_quantities
                ):
                    PlanItem.objects.create(
                        plan=existing_plan,
                        product_id=product_id,
                        planned_quantity=quantity,
                        completed_quantity=completed_quantity or 0,
                    )

                return JsonResponse(
                    {
                        "status": "success",
                        "message": "План успешно обновлен",
                        "plan_id": existing_plan.id,
                    }
                )
            else:
                # Создаем новый план
                plan = Plan.objects.create(
                    line=line,
                    shift=shift,
                    date=date,
                    status=status,
                    created_by=request.user,
                )

                # Добавляем позиции плана
                for product_id, quantity, completed_quantity in zip(
                    products, quantities, completed_quantities
                ):
                    PlanItem.objects.create(
                        plan=plan,
                        product_id=product_id,
                        planned_quantity=quantity,
                        completed_quantity=completed_quantity or 0,
                    )

                return JsonResponse(
                    {
                        "status": "success",
                        "message": "План успешно создан",
                        "plan_id": plan.id,
                    }
                )

        except Line.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Линия не найдена"})
        except Shift.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Смена не найдена"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "error", "message": "Метод не поддерживается"})


@login_required
def get_plan(request, plan_id):
    """Получить данные плана для редактирования."""
    try:
        plan = Plan.objects.get(id=plan_id)
        items = []
        for item in plan.items.all():
            items.append(
                {
                    "product_id": item.product.id,
                    "planned_quantity": item.planned_quantity,
                    "completed_quantity": item.completed_quantity,
                }
            )

        data = {
            "status": "success",
            "plan": {
                "shift_id": plan.shift.id,
                "status": plan.status,
                "items": items,
            },
        }
        return JsonResponse(data)
    except Plan.DoesNotExist:
        return JsonResponse({"status": "error", "message": "План не найден"})
    except Exception as e:
        logger.error(f"Error getting plan: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)})


@login_required
@require_POST
def edit_plan(request, plan_id):
    """Редактирование существующего плана."""
    try:
        plan = get_object_or_404(Plan, id=plan_id)

        # Обновляем основные данные плана
        shift_id = request.POST.get("shift")
        status = request.POST.get("status")

        if shift_id:
            shift = get_object_or_404(Shift, id=shift_id)
            plan.shift = shift

        if status:
            plan.status = status

        plan.save()

        # Обновляем продукты
        products = request.POST.getlist("products[]")
        quantities = request.POST.getlist("quantities[]")
        completed_quantities = request.POST.getlist("completed_quantities[]")

        if not products or not quantities:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Необходимо указать хотя бы один продукт и его количество",
                }
            )

        # Удаляем старые позиции
        plan.items.all().delete()

        # Добавляем новые позиции
        for product_id, quantity, completed_quantity in zip(
            products, quantities, completed_quantities
        ):
            if product_id and quantity:
                try:
                    product = get_object_or_404(Product, id=product_id)
                    quantity = int(quantity)
                    completed_quantity = int(completed_quantity or 0)
                    PlanItem.objects.create(
                        plan=plan,
                        product=product,
                        planned_quantity=quantity,
                        completed_quantity=completed_quantity,
                    )
                except ValueError:
                    return JsonResponse(
                        {
                            "status": "error",
                            "message": f"Некорректное количество для продукта {product_id}: {quantity}",
                        }
                    )
                except Exception as e:
                    return JsonResponse(
                        {
                            "status": "error",
                            "message": f"Ошибка при добавлении продукта: {str(e)}",
                        }
                    )

        return JsonResponse({"status": "success"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})
