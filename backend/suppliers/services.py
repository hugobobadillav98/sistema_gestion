# suppliers/services.py

from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Supplier, SupplierAccount


def create_purchase(supplier, amount, invoice_number, due_date=None, 
                   installments=1, notes='', created_by=None):
    """Registrar una compra a crédito"""
    
    tenant = supplier.tenant
    
    # Calcular fecha de vencimiento si no se proporciona
    if not due_date:
        due_date = timezone.now().date() + timedelta(days=supplier.payment_terms_days)
    
    with transaction.atomic():
        if installments == 1:
            # Compra simple (sin cuotas)
            purchase = SupplierAccount.objects.create(
                tenant=tenant,
                supplier=supplier,
                transaction_type='purchase',
                amount=amount,
                transaction_date=timezone.now().date(),
                due_date=due_date,
                invoice_number=invoice_number,
                notes=notes,
                total_installments=1,
                installment_number=1,
                created_by=created_by
            )
            return purchase
        
        else:
            # Compra en cuotas
            # Crear transacción padre
            parent_purchase = SupplierAccount.objects.create(
                tenant=tenant,
                supplier=supplier,
                transaction_type='purchase',
                amount=amount,
                transaction_date=timezone.now().date(),
                due_date=due_date,
                invoice_number=invoice_number,
                notes=f"{notes} - Compra en {installments} cuotas",
                total_installments=installments,
                installment_number=0,  # Padre
                created_by=created_by
            )
            
            # Crear cuotas
            amount_per_installment = amount / installments
            installment_list = []
            
            for i in range(1, installments + 1):
                # Calcular fecha de vencimiento de cada cuota
                installment_due_date = due_date + timedelta(days=30 * (i - 1))
                
                installment = SupplierAccount.objects.create(
                    tenant=tenant,
                    supplier=supplier,
                    transaction_type='purchase',
                    amount=amount_per_installment,
                    transaction_date=timezone.now().date(),
                    due_date=installment_due_date,
                    invoice_number=f"{invoice_number}-{i}",
                    notes=f"Cuota {i} de {installments}",
                    total_installments=installments,
                    installment_number=i,
                    parent_transaction=parent_purchase,
                    created_by=created_by
                )
                installment_list.append(installment)
            
            return parent_purchase


def create_payment(supplier, amount, payment_method, related_purchase=None,
                  reference='', notes='', created_by=None):
    """Registrar un pago a proveedor"""
    
    tenant = supplier.tenant
    
    with transaction.atomic():
        payment = SupplierAccount.objects.create(
            tenant=tenant,
            supplier=supplier,
            transaction_type='payment',
            amount=amount,
            transaction_date=timezone.now().date(),
            payment_method=payment_method,
            related_purchase=related_purchase,
            reference=reference,
            notes=notes,
            created_by=created_by
        )
        
        # Si el pago es para una compra específica, marcarla como pagada
        if related_purchase and related_purchase.amount == amount:
            related_purchase.paid_date = timezone.now().date()
            related_purchase.save()
        
        return payment


def get_suppliers_with_overdue_debt(tenant):
    """Obtener proveedores con deuda vencida"""
    from django.db.models import Q
    
    suppliers = Supplier.objects.filter(
        tenant=tenant,
        is_active=True
    )
    
    overdue_suppliers = []
    
    for supplier in suppliers:
        if supplier.has_overdue_debt():
            overdue_suppliers.append(supplier)
    
    return overdue_suppliers


def get_accounts_payable_summary(tenant):
    """Resumen de cuentas a pagar"""
    from django.db.models import Sum
    
    # Total adeudado
    total_debt = 0
    overdue_debt = 0
    due_this_week = 0
    due_this_month = 0
    
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)
    
    today = timezone.now().date()
    week_end = today + timedelta(days=7)
    month_end = today + timedelta(days=30)
    
    for supplier in suppliers:
        balance = supplier.get_balance()
        total_debt += balance
        
        # Deuda vencida
        overdue_purchases = supplier.supplieraccount_set.filter(
            transaction_type='purchase',
            due_date__lt=today,
            paid_date__isnull=True
        )
        overdue_debt += sum(p.amount for p in overdue_purchases)
        
        # Vence esta semana
        due_week = supplier.supplieraccount_set.filter(
            transaction_type='purchase',
            due_date__gte=today,
            due_date__lte=week_end,
            paid_date__isnull=True
        )
        due_this_week += sum(p.amount for p in due_week)
        
        # Vence este mes
        due_month = supplier.supplieraccount_set.filter(
            transaction_type='purchase',
            due_date__gte=today,
            due_date__lte=month_end,
            paid_date__isnull=True
        )
        due_this_month += sum(p.amount for p in due_month)
    
    return {
        'total_debt': total_debt,
        'overdue_debt': overdue_debt,
        'due_this_week': due_this_week,
        'due_this_month': due_this_month,
        'suppliers_count': suppliers.count(),
        'overdue_suppliers_count': len(get_suppliers_with_overdue_debt(tenant))
    }
