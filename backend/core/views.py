from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F
from django.utils import timezone
from datetime import timedelta

from sales.models import Sale
from stock.models import Product
from customers.models import Customer


@login_required
def dashboard_view(request):
    """
    Main dashboard with key metrics.
    """
    if not request.tenant:
        return redirect('admin:index')
    
    # Today's date
    today = timezone.now().date()
    
    # Sales today
    sales_today = Sale.objects.filter(
        tenant=request.tenant,
        sale_date__date=today,
        status='completed'
    ).aggregate(
        total=Sum('total_amount'),
        count=Count('id')
    )
    
    # Sales this month
    month_start = today.replace(day=1)
    sales_month = Sale.objects.filter(
        tenant=request.tenant,
        sale_date__date__gte=month_start,
        status='completed'
    ).aggregate(
        total=Sum('total_amount'),
        count=Count('id')
    )
    
    # Low stock products
    low_stock = Product.objects.filter(
        tenant=request.tenant,
        is_active=True,
        current_stock__lte=F('minimum_stock')
    ).count()
    
    # Customers with debt
    customers_debt = Customer.objects.filter(
        tenant=request.tenant,
        is_active=True,
        current_balance__gt=0 
    ).aggregate(
        total_debt=Sum('current_balance'), 
        count=Count('id')
    )
    
    # Recent sales
    recent_sales = Sale.objects.filter(
        tenant=request.tenant
    ).select_related('customer').order_by('-sale_date')[:10]
    
    context = {
        'sales_today': sales_today,
        'sales_month': sales_month,
        'low_stock_count': low_stock,
        'customers_debt': customers_debt,
        'recent_sales': recent_sales,
        'tenant': request.tenant,
    }
    
    return render(request, 'core/dashboard.html', context)
