from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal

from core.models import TenantUser
from core.views import get_user_tenant
from .models import Quote, QuoteItem
from customers.models import Customer
from stock.models import Product


def _require_tenant(request):
    tenant = get_user_tenant(request)
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return None
    return tenant


@login_required
def quote_list(request):
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    quotes = Quote.objects.filter(tenant=tenant).select_related('customer').order_by('-created_date')
    return render(request, 'quotes/list.html', {'quotes': quotes, 'tenant': tenant})


@login_required
def quote_create(request):
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    customers = Customer.objects.filter(tenant=tenant, is_active=True).order_by('name')
    products = Product.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        validity_days = int(request.POST.get('validity_days', '7'))
        
        # Si no eligió cliente, queda en None (NULL en la BD)
        customer = None
        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id, tenant=tenant)
        
        quote = Quote.objects.create(
            tenant=tenant,
            quote_number=f'Q-{timezone.now().strftime("%Y%m%d%H%M%S")}',
            customer=customer,  # Puede ser None
            issue_date=timezone.now().date(),
            valid_until=timezone.now().date() + timezone.timedelta(days=validity_days),
            status='draft',
            created_by=request.user,
        )
        
        return redirect('quotes:edit', pk=quote.pk)
    
    return render(request, 'quotes/create.html', {
        'tenant': tenant,
        'customers': customers,
        'products': products,
    })



@login_required
def quote_detail(request, pk):
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    quote = get_object_or_404(Quote, pk=pk, tenant=tenant)
    items = quote.items.select_related('product')
    
    return render(request, 'quotes/detail.html', {
        'tenant': tenant,
        'quote': quote,
        'items': items,
    })


@login_required
def quote_edit(request, pk):
    """
    Editar un presupuesto: agregar/quitar productos y cambiar cantidades/precios.
    """
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    quote = get_object_or_404(Quote, pk=pk, tenant=tenant)
    
    if not quote.can_be_edited():
        messages.error(request, 'Este presupuesto ya no puede ser editado.')
        return redirect('quotes:detail', pk=quote.pk)
    
    products = Product.objects.filter(tenant=tenant, is_active=True)
    items = quote.items.select_related('product')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 1) Agregar producto
        if action == 'add_item':
            product_id = request.POST.get('product_id')
            qty = request.POST.get('quantity') or '1'
            price = request.POST.get('unit_price')  # opcional
            
            product = get_object_or_404(Product, pk=product_id, tenant=tenant)
            
            try:
                quantity = Decimal(qty.replace(',', '.'))
            except Exception:
                messages.error(request, 'Cantidad inválida.')
                return redirect('quotes:edit', pk=quote.pk)
            
            if quantity <= 0:
                messages.error(request, 'La cantidad debe ser mayor a 0.')
                return redirect('quotes:edit', pk=quote.pk)
            
            # precio: si no se envía, usar el del producto
            if price:
                unit_price = Decimal(price.replace(',', '.'))
            else:
                unit_price = product.default_unit_price_for_quotes
            
            QuoteItem.objects.create(
                quote=quote,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
            )
            
            messages.success(request, 'Producto agregado al presupuesto.')
            return redirect('quotes:edit', pk=quote.pk)
        
        # 2) Actualizar items existentes
        if action == 'save_items':
            for item in items:
                qty_str = request.POST.get(f'qty_{item.id}')
                price_str = request.POST.get(f'price_{item.id}')
                
                try:
                    qty = Decimal(qty_str.replace(',', '.'))
                    price = Decimal(price_str.replace(',', '.'))
                except Exception:
                    messages.error(request, 'Valores inválidos en items.')
                    return redirect('quotes:edit', pk=quote.pk)
                
                if qty <= 0:
                    # si la cantidad es 0 o negativa, borramos el ítem
                    item.delete()
                else:
                    item.quantity = qty
                    item.unit_price = price
                    item.save()
            
            messages.success(request, 'Items actualizados.')
            return redirect('quotes:edit', pk=quote.pk)
        
        # 3) Eliminar un ítem específico
        if action == 'delete_item':
            item_id = request.POST.get('item_id')
            item = get_object_or_404(QuoteItem, pk=item_id, quote=quote)
            item.delete()
            messages.success(request, 'Item eliminado.')
            return redirect('quotes:edit', pk=quote.pk)
    
    return render(request, 'quotes/edit.html', {
        'tenant': tenant,
        'quote': quote,
        'items': items,
        'products': products,
    })

@login_required
def quote_send(request, pk):
    """Marcar presupuesto como ENVIADO."""
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    quote = get_object_or_404(Quote, pk=pk, tenant=tenant)
    
    if not quote.can_be_edited():
        messages.error(request, 'Este presupuesto no puede cambiar a enviado.')
        return redirect('quotes:detail', pk=quote.pk)
    
    quote.status = 'sent'
    quote.save(update_fields=['status'])
    messages.success(request, 'Presupuesto marcado como enviado.')
    return redirect('quotes:detail', pk=quote.pk)


@login_required
def quote_approve(request, pk):
    """Marcar presupuesto como APROBADO (solo cambia estado por ahora)."""
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    quote = get_object_or_404(Quote, pk=pk, tenant=tenant)
    
    if quote.status != 'sent':
        messages.error(request, 'Solo se pueden aprobar presupuestos enviados.')
        return redirect('quotes:detail', pk=quote.pk)
    
    quote.status = 'approved'
    quote.save(update_fields=['status'])
    messages.success(request, 'Presupuesto aprobado. (Luego lo convertiremos a pedido).')
    return redirect('quotes:detail', pk=quote.pk)


@login_required
def quote_reject(request, pk):
    """Marcar presupuesto como RECHAZADO."""
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    quote = get_object_or_404(Quote, pk=pk, tenant=tenant)
    
    if quote.status not in ['sent', 'approved']:
        messages.error(request, 'Solo se pueden rechazar presupuestos enviados o aprobados.')
        return redirect('quotes:detail', pk=quote.pk)
    
    quote.status = 'rejected'
    quote.save(update_fields=['status'])
    messages.success(request, 'Presupuesto rechazado.')
    return redirect('quotes:detail', pk=quote.pk)


@login_required
def quote_convert_to_order(request, pk):
    """Convertir presupuesto aprobado en pedido"""
    from orders.models import Order, OrderItem
    
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    quote = get_object_or_404(Quote, pk=pk, tenant=tenant)
    
    # Validaciones
    if quote.status != 'approved':
        messages.error(request, 'Solo se pueden convertir presupuestos aprobados.')
        return redirect('quotes:detail', pk=quote.pk)
    
    if quote.converted_to_order:
        messages.error(request, 'Este presupuesto ya fue convertido a pedido.')
        return redirect('quotes:detail', pk=quote.pk)
    
    if quote.items.count() == 0:
        messages.error(request, 'No se puede convertir un presupuesto sin ítems.')
        return redirect('quotes:detail', pk=quote.pk)
    
    # ← AGREGAR ESTA VALIDACIÓN
    if not quote.customer:
        messages.error(request, 'Debe asignar un cliente específico antes de convertir a pedido.')
        return redirect('quotes:detail', pk=quote.pk)
    
    # Crear el pedido
    order = Order.objects.create(
        tenant=tenant,
        order_number=f'PED-{timezone.now().strftime("%Y%m%d%H%M%S")}',
        customer=quote.customer,
        quote=quote,
        order_date=timezone.now().date(),
        status='pending',
        created_by=request.user,
    )
    
    # Copiar items del presupuesto al pedido
    for quote_item in quote.items.all():
        OrderItem.objects.create(
            order=order,
            product=quote_item.product,
            quantity=quote_item.quantity,
            unit_price=quote_item.unit_price,
            tax_type=quote_item.tax_type,
            tax_rate=quote_item.tax_rate,
        )
    
    # Marcar presupuesto como convertido
    quote.converted_to_order = True
    quote.converted_date = timezone.now()
    quote.save(update_fields=['converted_to_order', 'converted_date'])
    
    messages.success(request, f'Pedido {order.order_number} creado exitosamente desde presupuesto {quote.quote_number}.')
    return redirect('orders:detail', pk=order.pk)


@login_required
def quote_assign_customer(request, pk):
    """Asignar cliente a un presupuesto que tiene Cliente General"""
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    quote = get_object_or_404(Quote, pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id, tenant=tenant)
            quote.customer = customer
            quote.save(update_fields=['customer'])
            messages.success(request, f'Cliente {customer.name} asignado al presupuesto {quote.quote_number}.')
        return redirect('quotes:detail', pk=quote.pk)
    
    # GET: Mostrar formulario
    customers = Customer.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    return render(request, 'quotes/assign_customer.html', {
        'tenant': tenant,
        'quote': quote,
        'customers': customers,
    })
