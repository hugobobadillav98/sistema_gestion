from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal

from .models import CashRegister, Sale


@login_required
def cash_register_status(request):
    """Show current cash register status."""
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    # Get open cash register
    open_register = CashRegister.objects.filter(
        tenant=request.tenant,
        status='open'
    ).first()
    
    # Get recent closed registers
    closed_registers = CashRegister.objects.filter(
        tenant=request.tenant,
        status='closed'
    )[:10]
    
    context = {
        'open_register': open_register,
        'closed_registers': closed_registers,
    }
    
    if open_register:
        # Get sales summary
        sales = open_register.get_total_sales()
        
        sales_by_currency = {
            'PYG': sales.filter(currency_paid='PYG').aggregate(
                total=Sum('paid_amount_original'),
                count=Count('id')
            ),
            'USD': sales.filter(currency_paid='USD').aggregate(
                total=Sum('paid_amount_original'),
                count=Count('id')
            ),
            'BRL': sales.filter(currency_paid='BRL').aggregate(
                total=Sum('paid_amount_original'),
                count=Count('id')
            ),
        }
        
        context['sales_summary'] = sales_by_currency
        context['total_sales'] = sales.count()
    
    return render(request, 'sales/cash_register_status.html', context)


@login_required
def open_cash_register(request):
    """Open a new cash register."""
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    # Check if there's already an open register
    open_register = CashRegister.objects.filter(
        tenant=request.tenant,
        status='open'
    ).first()
    
    if open_register:
        messages.warning(request, "Ya hay una caja abierta")
        return redirect('sales:cash_register_status')
    
    if request.method == 'POST':
        initial_pyg = Decimal(request.POST.get('initial_pyg', '0') or '0')
        initial_usd = Decimal(request.POST.get('initial_usd', '0') or '0')
        initial_brl = Decimal(request.POST.get('initial_brl', '0') or '0')
        notes = request.POST.get('notes', '')
        
        cash_register = CashRegister.objects.create(
            tenant=request.tenant,
            opened_by=request.user,
            initial_amount_pyg=initial_pyg,
            initial_amount_usd=initial_usd,
            initial_amount_brl=initial_brl,
            notes=notes,
            status='open'
        )
        
        messages.success(request, f"Caja abierta exitosamente")
        return redirect('sales:cash_register_status')
    
    return render(request, 'sales/open_cash_register.html')


@login_required
def close_cash_register(request, pk):
    """Close cash register with counting."""
    cash_register = get_object_or_404(
        CashRegister,
        id=pk,
        tenant=request.tenant,
        status='open'
    )
    
    if request.method == 'POST':
        actual_pyg = Decimal(request.POST.get('actual_pyg', '0') or '0')
        actual_usd = Decimal(request.POST.get('actual_usd', '0') or '0')
        actual_brl = Decimal(request.POST.get('actual_brl', '0') or '0')
        notes = request.POST.get('notes', '')
        
        # Calculate expected amounts
        sales = cash_register.get_total_sales()
        
        expected_pyg = cash_register.initial_amount_pyg + (
            sales.filter(currency_paid='PYG', payment_method='cash')
            .aggregate(total=Sum('paid_amount_original'))['total'] or 0
        )
        
        expected_usd = cash_register.initial_amount_usd + (
            sales.filter(currency_paid='USD', payment_method='cash')
            .aggregate(total=Sum('paid_amount_original'))['total'] or 0
        )
        
        expected_brl = cash_register.initial_amount_brl + (
            sales.filter(currency_paid='BRL', payment_method='cash')
            .aggregate(total=Sum('paid_amount_original'))['total'] or 0
        )
        
        # Calculate differences
        diff_pyg = actual_pyg - expected_pyg
        diff_usd = actual_usd - expected_usd
        diff_brl = actual_brl - expected_brl
        
        # Update cash register
        cash_register.closed_at = timezone.now()
        cash_register.closed_by = request.user
        cash_register.expected_amount_pyg = expected_pyg
        cash_register.expected_amount_usd = expected_usd
        cash_register.expected_amount_brl = expected_brl
        cash_register.actual_amount_pyg = actual_pyg
        cash_register.actual_amount_usd = actual_usd
        cash_register.actual_amount_brl = actual_brl
        cash_register.difference_pyg = diff_pyg
        cash_register.difference_usd = diff_usd
        cash_register.difference_brl = diff_brl
        cash_register.status = 'closed'
        if notes:
            cash_register.notes += f"\nCierre: {notes}"
        cash_register.save()
        
        messages.success(request, "Caja cerrada exitosamente")
        return redirect('sales:cash_register_detail', pk=cash_register.pk)
    
    # Calculate expected for display
    sales = cash_register.get_total_sales()
    
    sales_cash = {
        'PYG': sales.filter(currency_paid='PYG', payment_method='cash').aggregate(
            total=Sum('paid_amount_original')
        )['total'] or 0,
        'USD': sales.filter(currency_paid='USD', payment_method='cash').aggregate(
            total=Sum('paid_amount_original')
        )['total'] or 0,
        'BRL': sales.filter(currency_paid='BRL', payment_method='cash').aggregate(
            total=Sum('paid_amount_original')
        )['total'] or 0,
    }
    
    context = {
        'cash_register': cash_register,
        'sales_cash': sales_cash,
        'expected_pyg': cash_register.initial_amount_pyg + sales_cash['PYG'],
        'expected_usd': cash_register.initial_amount_usd + sales_cash['USD'],
        'expected_brl': cash_register.initial_amount_brl + sales_cash['BRL'],
    }
    
    return render(request, 'sales/close_cash_register.html', context)


@login_required
def cash_register_detail(request, pk):
    """View cash register details and report."""
    cash_register = get_object_or_404(
        CashRegister,
        id=pk,
        tenant=request.tenant
    )
    
    sales = cash_register.get_total_sales()
    
    # Sales by payment method
    sales_by_method = {}
    for method, label in Sale.PAYMENT_METHOD_CHOICES:
        sales_by_method[label] = sales.filter(payment_method=method).aggregate(
            count=Count('id'),
            total=Sum('total_amount')
        )
    
    # AGREGÁ ESTO - Calcular ventas por moneda
    sales_pyg = cash_register.expected_amount_pyg - cash_register.initial_amount_pyg
    sales_usd = cash_register.expected_amount_usd - cash_register.initial_amount_usd
    sales_brl = cash_register.expected_amount_brl - cash_register.initial_amount_brl
    
    context = {
        'cash_register': cash_register,
        'sales': sales,
        'sales_by_method': sales_by_method,
        'sales_pyg': sales_pyg,  # NUEVO
        'sales_usd': sales_usd,  # NUEVO
        'sales_brl': sales_brl,  # NUEVO
    }
    
    return render(request, 'sales/cash_register_detail.html', context)

