from django.utils import timezone
from django.db.models import Sum, Q
from .models import CustomerAccount, Customer


def customer_alerts(request):
    """Add customer alerts to all templates."""
    context = {
        'overdue_count': 0,
        'overdue_amount': 0,
        'due_soon_count': 0,
    }
    
    if not hasattr(request, 'tenant') or not request.tenant:
        return context
    
    tenant = request.tenant
    today = timezone.now().date()
    
    # Clientes con pagos vencidos
    overdue = CustomerAccount.objects.filter(
        tenant=tenant,
        transaction_type='sale',
        due_date__lt=today
    ).aggregate(
        count=Sum('amount'),
        total=Sum('amount')
    )
    
    context['overdue_count'] = CustomerAccount.objects.filter(
        tenant=tenant,
        transaction_type='sale',
        due_date__lt=today
    ).values('customer').distinct().count()
    
    context['overdue_amount'] = overdue['total'] or 0
    
    # Pagos que vencen en los próximos 7 días
    from datetime import timedelta
    next_week = today + timedelta(days=7)
    
    context['due_soon_count'] = CustomerAccount.objects.filter(
        tenant=tenant,
        transaction_type='sale',
        due_date__gte=today,
        due_date__lte=next_week
    ).values('customer').distinct().count()
    
    return context
