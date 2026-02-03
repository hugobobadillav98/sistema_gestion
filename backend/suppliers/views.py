# suppliers/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Supplier, SupplierAccount
from . import services


def get_user_tenant(request):
    """Helper para obtener el tenant del usuario actual"""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    
    # Si no está en request (por alguna razón), obtenerlo de TenantUser
    membership = request.user.tenant_memberships.filter(is_active=True).first()
    return membership.tenant if membership else None


@login_required
def dashboard(request):
    """Dashboard de cuentas a pagar"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('/')
    
    summary = services.get_accounts_payable_summary(tenant)
    overdue_suppliers = services.get_suppliers_with_overdue_debt(tenant)
    
    context = {
        'summary': summary,
        'overdue_suppliers': overdue_suppliers,
    }
    
    return render(request, 'suppliers/accounts_payable_dashboard.html', context)


@login_required
def supplier_list(request):
    """Lista de proveedores"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('/')
    
    # Búsqueda
    search = request.GET.get('search', '')
    suppliers = Supplier.objects.filter(tenant=tenant)
    
    if search:
        suppliers = suppliers.filter(
            Q(name__icontains=search) |
            Q(tax_id__icontains=search) |
            Q(phone__icontains=search)
        )
    
    # Filtro de activos/inactivos
    status = request.GET.get('status', 'active')
    if status == 'active':
        suppliers = suppliers.filter(is_active=True)
    elif status == 'inactive':
        suppliers = suppliers.filter(is_active=False)
    
    # Agregar saldo a cada proveedor
    suppliers_with_balance = []
    for supplier in suppliers:
        supplier.balance = supplier.get_balance()
        supplier.has_overdue = supplier.has_overdue_debt()
        suppliers_with_balance.append(supplier)
    
    context = {
        'suppliers': suppliers_with_balance,
        'search': search,
        'status': status,
    }
    
    return render(request, 'suppliers/supplier_list.html', context)


@login_required
def supplier_detail(request, supplier_id):
    """Detalle de proveedor y cuenta corriente"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('/')
    
    supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
    
    # Movimientos de cuenta
    transactions = SupplierAccount.objects.filter(
        tenant=tenant,
        supplier=supplier
    ).order_by('-transaction_date', '-created_at')
    
    # Solo mostrar cuotas hijas (no padres)
    transactions = transactions.filter(
        Q(installment_number__gt=0) | Q(transaction_type='payment') | Q(transaction_type='adjustment')
    )
    
    # Calcular balance
    balance = supplier.get_balance()
    
    # Compras pendientes (no pagadas)
    pending_purchases = transactions.filter(
        transaction_type='purchase',
        paid_date__isnull=True
    )
    
    context = {
        'supplier': supplier,
        'transactions': transactions,
        'balance': balance,
        'pending_purchases': pending_purchases,
    }
    
    return render(request, 'suppliers/supplier_detail.html', context)


@login_required
def supplier_create(request):
    """Crear nuevo proveedor"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('/')
    
    if request.method == 'POST':
        supplier = Supplier.objects.create(
            tenant=tenant,
            name=request.POST['name'],
            tax_id=request.POST.get('tax_id', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            address=request.POST.get('address', ''),
            payment_terms_days=int(request.POST.get('payment_terms_days', 30)),
            credit_limit=float(request.POST.get('credit_limit', 0)),
            contact_person=request.POST.get('contact_person', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user
        )
        
        messages.success(request, f'Proveedor {supplier.name} creado exitosamente.')
        return redirect('suppliers:detail', supplier_id=supplier.id)
    
    return render(request, 'suppliers/supplier_form.html')


@login_required
def purchase_create(request):
    """Registrar compra a crédito"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('/')
    
    if request.method == 'POST':
        supplier = get_object_or_404(Supplier, id=request.POST['supplier_id'], tenant=tenant)
        amount = float(request.POST['amount'])
        invoice_number = request.POST['invoice_number']
        due_date = request.POST.get('due_date') or None
        installments = int(request.POST.get('installments', 1))
        notes = request.POST.get('notes', '')
        
        purchase = services.create_purchase(
            supplier=supplier,
            amount=amount,
            invoice_number=invoice_number,
            due_date=due_date,
            installments=installments,
            notes=notes,
            created_by=request.user
        )
        
        messages.success(request, f'Compra registrada exitosamente. Total: ₲{amount:,.0f}')
        return redirect('suppliers:detail', supplier_id=supplier.id)
    
    # GET
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'suppliers': suppliers,
    }
    
    return render(request, 'suppliers/purchase_form.html', context)


@login_required
def payment_create(request):
    """Registrar pago a proveedor"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('/')
    
    if request.method == 'POST':
        supplier = get_object_or_404(Supplier, id=request.POST['supplier_id'], tenant=tenant)
        amount = float(request.POST['amount'])
        payment_method = request.POST['payment_method']
        reference = request.POST.get('reference', '')
        notes = request.POST.get('notes', '')
        
        # Si seleccionó una compra específica para pagar
        related_purchase_id = request.POST.get('related_purchase_id')
        related_purchase = None
        if related_purchase_id:
            related_purchase = get_object_or_404(
                SupplierAccount, 
                id=related_purchase_id, 
                tenant=tenant
            )
        
        payment = services.create_payment(
            supplier=supplier,
            amount=amount,
            payment_method=payment_method,
            related_purchase=related_purchase,
            reference=reference,
            notes=notes,
            created_by=request.user
        )
        
        messages.success(request, f'Pago de ₲{amount:,.0f} registrado exitosamente.')
        return redirect('suppliers:detail', supplier_id=supplier.id)
    
    # GET
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)
    
    # Si viene con supplier_id en query params
    selected_supplier_id = request.GET.get('supplier_id')
    pending_purchases = []
    
    if selected_supplier_id:
        supplier = get_object_or_404(Supplier, id=selected_supplier_id, tenant=tenant)
        pending_purchases = SupplierAccount.objects.filter(
            tenant=tenant,
            supplier=supplier,
            transaction_type='purchase',
            paid_date__isnull=True,
            installment_number__gt=0
        )
    
    context = {
        'suppliers': suppliers,
        'selected_supplier_id': selected_supplier_id,
        'pending_purchases': pending_purchases,
    }
    
    return render(request, 'suppliers/payment_form.html', context)


@login_required
def supplier_edit(request, supplier_id):
    """Editar proveedor"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('/')
    
    supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
    
    if request.method == 'POST':
        # Actualizar datos
        supplier.name = request.POST['name']
        supplier.tax_id = request.POST.get('tax_id', '')
        supplier.email = request.POST.get('email', '')
        supplier.phone = request.POST.get('phone', '')
        supplier.address = request.POST.get('address', '')
        supplier.payment_terms_days = int(request.POST.get('payment_terms_days', 30))
        supplier.credit_limit = float(request.POST.get('credit_limit', 0))
        supplier.contact_person = request.POST.get('contact_person', '')
        supplier.notes = request.POST.get('notes', '')
        supplier.save()
        
        messages.success(request, f'Proveedor {supplier.name} actualizado exitosamente.')
        return redirect('suppliers:detail', supplier_id=supplier.id)
    
    context = {
        'supplier': supplier,
        'is_edit': True,
    }
    
    return render(request, 'suppliers/supplier_form.html', context)


@login_required
def supplier_toggle_active(request, supplier_id):
    """Activar/Desactivar proveedor"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('/')
    
    supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
    
    # Toggle active status
    supplier.is_active = not supplier.is_active
    supplier.save()
    
    status_text = "activado" if supplier.is_active else "desactivado"
    messages.success(request, f'Proveedor {supplier.name} {status_text} exitosamente.')
    
    return redirect('suppliers:detail', supplier_id=supplier.id)