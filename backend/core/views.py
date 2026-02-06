# core/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import logout
from django.contrib import messages
from django.db import transaction
from decimal import Decimal

from sales.models import Sale
from stock.models import Product
from customers.models import Customer
from .models import Tenant, ExchangeRate


def get_user_tenant(request):
    """Helper para obtener el tenant del usuario actual"""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    membership = request.user.tenant_memberships.filter(is_active=True).first()
    return membership.tenant if membership else None


def logout_view(request):
    """Cerrar sesión - acepta GET y POST"""
    logout(request)
    messages.success(request, 'Sesión cerrada exitosamente.')
    return redirect('login')


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


# ==============================
# CONFIGURACIÓN
# ==============================

@login_required
def settings_view(request):
    """Página principal de configuración"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    # Obtener tasas de cambio
    exchange_rates = ExchangeRate.objects.all()
    
    # Obtener rol del usuario
    tenant_user = request.user.tenant_memberships.filter(
        tenant=tenant,
        is_active=True
    ).first()
    
    context = {
        'tenant': tenant,
        'exchange_rates': exchange_rates,
        'user_role': tenant_user.role if tenant_user else None,
    }
    return render(request, 'core/settings.html', context)


@login_required
def business_settings(request):
    """Editar información del negocio"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    # Verificar permisos (solo owner/admin)
    tenant_user = request.user.tenant_memberships.filter(
        tenant=tenant,
        is_active=True
    ).first()
    
    if not tenant_user or tenant_user.role not in ['owner', 'admin']:
        messages.error(request, 'No tiene permisos para editar la configuración.')
        return redirect('settings')
    
    if request.method == 'POST':
        tenant.name = request.POST.get('name', tenant.name)
        tenant.tax_id = request.POST.get('tax_id', '')
        tenant.phone = request.POST.get('phone', '')
        tenant.email = request.POST.get('email', '')
        tenant.address = request.POST.get('address', '')
        tenant.save()
        
        messages.success(request, 'Información del negocio actualizada.')
        return redirect('settings')
    
    context = {
        'tenant': tenant,
    }
    return render(request, 'core/business_settings.html', context)


@login_required
def exchange_rates(request):
    """Gestionar tasas de cambio"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    # Verificar permisos (solo owner/admin)
    tenant_user = request.user.tenant_memberships.filter(
        tenant=tenant,
        is_active=True
    ).first()
    
    if not tenant_user or tenant_user.role not in ['owner', 'admin']:
        messages.error(request, 'No tiene permisos para editar tasas de cambio.')
        return redirect('settings')
    
    if request.method == 'POST':
        try:
            # Actualizar tasas
            for currency in ['USD', 'BRL', 'PYG']:
                rate_value = request.POST.get(f'rate_{currency}')
                if rate_value:
                    rate_decimal = Decimal(rate_value.replace(',', ''))
                    
                    ExchangeRate.objects.update_or_create(
                        currency=currency,
                        defaults={'rate_to_pyg': rate_decimal}
                    )
            
            messages.success(request, 'Tasas de cambio actualizadas.')
            return redirect('settings')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar tasas: {str(e)}')
    
    # Obtener tasas actuales
    rates = {}
    for currency in ['USD', 'BRL', 'PYG']:
        try:
            rate = ExchangeRate.objects.get(currency=currency)
            rates[currency] = rate
        except ExchangeRate.DoesNotExist:
            rates[currency] = None
    
    context = {
        'tenant': tenant,
        'rates': rates,
    }
    return render(request, 'core/exchange_rates.html', context)
