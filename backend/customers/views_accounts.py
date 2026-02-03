from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal

from .models import Customer, CustomerAccount
from sales.models import Sale


@login_required
def accounts_list(request):
    """List all customers with their balances."""
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    customers = Customer.objects.filter(
        tenant=request.tenant,
        is_active=True
    ).prefetch_related('account_transactions')
    
    # Calculate balances
    customers_with_balance = []
    total_debt = 0
    total_overdue = 0
    
    for customer in customers:
        balance = customer.get_balance()
        if balance > 0:  # Solo clientes con deuda
            overdue = customer.get_overdue_balance()
            customers_with_balance.append({
                'customer': customer,
                'balance': balance,
                'overdue': overdue,
            })
            total_debt += balance
            total_overdue += overdue
    
    # Sort by balance
    customers_with_balance.sort(key=lambda x: x['balance'], reverse=True)
    
    context = {
        'customers_with_balance': customers_with_balance,
        'total_debt': total_debt,
        'total_overdue': total_overdue,
    }
    
    return render(request, 'customers/accounts_list.html', context)


@login_required
def customer_account_detail(request, pk):
    """View customer account detail and transactions."""
    if not request.tenant:
        messages.error(request, 'No tenant found')
        return redirect('dashboard:index')
    
    tenant = request.tenant
    
    customer = get_object_or_404(
        Customer,
        id=pk,
        tenant=tenant
    )
    
    # Manejar actualización de fecha prometida
    if request.method == 'POST' and 'update_promised_date' in request.POST:
        transaction_id = request.POST.get('transaction_id')
        promised_date = request.POST.get('promised_date')
        
        if transaction_id and promised_date:
            try:
                transaction = CustomerAccount.objects.get(
                    id=transaction_id,
                    tenant=tenant,
                    customer=customer
                )
                transaction.promised_date = promised_date
                transaction.save()
                messages.success(request, 'Fecha prometida actualizada correctamente')
                return redirect('customers:customer_account_detail', pk=pk)
            except CustomerAccount.DoesNotExist:
                messages.error(request, 'Transacción no encontrada')
        else:
            messages.error(request, 'Datos incompletos')
    
    transactions = CustomerAccount.objects.filter(
        customer=customer,
        tenant=tenant
    ).select_related('sale', 'created_by').order_by('-transaction_date')
    
    balance = customer.get_balance()
    overdue = customer.get_overdue_balance()
    
    context = {
        'customer': customer,
        'transactions': transactions,
        'balance': balance,
        'overdue': overdue,
    }
    
    return render(request, 'customers/customer_account_detail.html', context)


@login_required
def register_payment(request, pk):
    """Register a payment for a customer."""
    customer = get_object_or_404(
        Customer,
        id=pk,
        tenant=request.tenant
    )
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', '0'))
        payment_method = request.POST.get('payment_method', 'cash')
        reference = request.POST.get('reference', '')
        notes = request.POST.get('notes', '')
        
        if amount <= 0:
            messages.error(request, "El monto debe ser mayor a cero")
            return redirect('customers:customer_account_detail', pk=pk)
        
        # Create payment transaction (negative amount = payment)
        CustomerAccount.objects.create(
            tenant=request.tenant,
            customer=customer,
            transaction_type='payment',
            amount=-amount,  # Negativo porque es pago
            payment_method=payment_method,
            reference=reference,
            notes=notes,
            created_by=request.user
        )
        
        messages.success(request, f"Pago de ₲{amount:,.0f} registrado exitosamente")
        return redirect('customers:customer_account_detail', pk=pk)
    
    balance = customer.get_balance()
    
    context = {
        'customer': customer,
        'balance': balance,
    }
    
    return render(request, 'customers/register_payment.html', context)


@login_required
def overdue_alerts(request):
    """View overdue payment alerts."""
    if not request.tenant:
        messages.error(request, 'No tenant found')
        return redirect('dashboard:index')
    
    tenant = request.tenant
    today = timezone.now().date()
    
    # Clientes con pagos vencidos
    overdue_customers = []
    customers_with_debt = Customer.objects.filter(
        tenant=tenant,
        account_transactions__transaction_type='sale'
    ).distinct()
    
    for customer in customers_with_debt:
        overdue_balance = customer.account_transactions.filter(
            transaction_type='sale',
            due_date__lt=today
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        if overdue_balance > 0:
            # Calcular días de atraso
            oldest_overdue = customer.account_transactions.filter(
                transaction_type='sale',
                due_date__lt=today
            ).order_by('due_date').first()
            
            days_overdue = (today - oldest_overdue.due_date).days if oldest_overdue else 0
            
            overdue_customers.append({
                'customer': customer,
                'overdue_balance': overdue_balance,
                'days_overdue': days_overdue,
                'total_balance': customer.get_balance()
            })
    
    # Ordenar por días de atraso (mayor a menor)
    overdue_customers.sort(key=lambda x: x['days_overdue'], reverse=True)
    
    # Pagos que vencen pronto (próximos 7 días)
    from datetime import timedelta
    next_week = today + timedelta(days=7)
    
    due_soon_customers = []
    for customer in customers_with_debt:
        due_soon_balance = customer.account_transactions.filter(
            transaction_type='sale',
            due_date__gte=today,
            due_date__lte=next_week
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        if due_soon_balance > 0:
            next_due = customer.account_transactions.filter(
                transaction_type='sale',
                due_date__gte=today,
                due_date__lte=next_week
            ).order_by('due_date').first()
            
            days_until_due = (next_due.due_date - today).days if next_due else 0
            
            due_soon_customers.append({
                'customer': customer,
                'due_soon_balance': due_soon_balance,
                'days_until_due': days_until_due,
                'due_date': next_due.due_date if next_due else None
            })
    
    # Ordenar por días hasta vencer (menor a mayor)
    due_soon_customers.sort(key=lambda x: x['days_until_due'])
    
    context = {
        'overdue_customers': overdue_customers,
        'due_soon_customers': due_soon_customers,
    }
    
    return render(request, 'customers/overdue_alerts.html', context)
