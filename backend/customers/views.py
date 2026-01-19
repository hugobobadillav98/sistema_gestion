from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Customer
from decimal import Decimal


@login_required
def customer_list(request):
    """Lista de clientes"""
    customers = Customer.objects.filter(tenant=request.tenant)
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        customers = customers.filter(
            Q(name__icontains=search) | 
            Q(tax_id__icontains=search) |
            Q(ruc__icontains=search) |
            Q(phone__icontains=search) |
            Q(mobile__icontains=search)
        )
    
    # Filtro por tipo
    customer_type = request.GET.get('type', '')
    if customer_type:
        customers = customers.filter(customer_type=customer_type)
    
    # Filtro por requiere factura
    requires_invoice = request.GET.get('requires_invoice', '')
    if requires_invoice:
        customers = customers.filter(requires_invoice=True)
    
    context = {
        'customers': customers,
        'search': search,
        'selected_type': customer_type,
    }
    return render(request, 'customers/customer_list.html', context)


@login_required
def customer_create(request):
    """Crear cliente"""
    if request.method == 'POST':
        try:
            customer = Customer(
                tenant=request.tenant,
                name=request.POST.get('name'),
                tax_id=request.POST.get('tax_id', ''),
                ruc=request.POST.get('ruc', '').strip() or None,
                dv=request.POST.get('dv', '').strip() or None,
                razon_social=request.POST.get('razon_social', ''),
                requires_invoice=request.POST.get('requires_invoice') == 'on',
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
                mobile=request.POST.get('mobile', ''),
                address=request.POST.get('address', ''),
                city=request.POST.get('city', ''),
                customer_type=request.POST.get('customer_type', 'retail'),
                credit_limit=Decimal(request.POST.get('credit_limit', 0)),
                notes=request.POST.get('notes', ''),
                is_active=request.POST.get('is_active') == 'on'
            )
            
            # Validar RUC si requiere factura
            if customer.requires_invoice and not customer.ruc:
                messages.error(request, 'Si requiere factura legal, debe ingresar el RUC.')
                return render(request, 'customers/customer_form.html', {'customer': customer})
            
            customer.save()
            messages.success(request, f'Cliente "{customer.name}" creado exitosamente.')
            return redirect('customers:customer_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear cliente: {str(e)}')
    
    return render(request, 'customers/customer_form.html', {})


@login_required
def customer_edit(request, pk):
    """Editar cliente"""
    customer = get_object_or_404(Customer, pk=pk, tenant=request.tenant)
    
    if request.method == 'POST':
        try:
            customer.name = request.POST.get('name')
            customer.tax_id = request.POST.get('tax_id', '')
            customer.ruc = request.POST.get('ruc', '').strip() or None
            customer.dv = request.POST.get('dv', '').strip() or None
            customer.razon_social = request.POST.get('razon_social', '')
            customer.requires_invoice = request.POST.get('requires_invoice') == 'on'
            customer.email = request.POST.get('email', '')
            customer.phone = request.POST.get('phone', '')
            customer.mobile = request.POST.get('mobile', '')
            customer.address = request.POST.get('address', '')
            customer.city = request.POST.get('city', '')
            customer.customer_type = request.POST.get('customer_type', 'retail')
            customer.credit_limit = Decimal(request.POST.get('credit_limit', 0))
            customer.notes = request.POST.get('notes', '')
            customer.is_active = request.POST.get('is_active') == 'on'
            
            # Validar RUC si requiere factura
            if customer.requires_invoice and not customer.ruc:
                messages.error(request, 'Si requiere factura legal, debe ingresar el RUC.')
                return render(request, 'customers/customer_form.html', {'customer': customer, 'is_edit': True})
            
            customer.save()
            messages.success(request, f'Cliente "{customer.name}" actualizado.')
            return redirect('customers:customer_list')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar: {str(e)}')
    
    context = {'customer': customer, 'is_edit': True}
    return render(request, 'customers/customer_form.html', context)


@login_required
def customer_delete(request, pk):
    """Eliminar cliente"""
    customer = get_object_or_404(Customer, pk=pk, tenant=request.tenant)
    
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f'Cliente "{name}" eliminado.')
        return redirect('customers:customer_list')
    
    return render(request, 'customers/customer_confirm_delete.html', {'customer': customer})
