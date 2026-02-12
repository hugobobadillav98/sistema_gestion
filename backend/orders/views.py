from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from core.models import TenantUser
from core.views import get_user_tenant
from .models import Order, OrderItem
from customers.models import Customer




def _require_tenant(request):
    tenant = get_user_tenant(request)
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return None
    return tenant




@login_required
def order_list(request):
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    orders = Order.objects.filter(tenant=tenant).select_related('customer').order_by('-created_date')
    return render(request, 'orders/list.html', {'orders': orders, 'tenant': tenant})




@login_required
def order_detail(request, pk):
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    items = order.items.select_related('product')
    
    return render(request, 'orders/detail.html', {
        'tenant': tenant,
        'order': order,
        'items': items,
    })




@login_required
def order_mark_in_progress(request, pk):
    """Marcar pedido como en proceso"""
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    
    if order.status == 'pending':
        order.status = 'in_progress'
        order.save(update_fields=['status'])
        messages.success(request, f'Pedido {order.order_number} marcado como En Proceso.')
    else:
        messages.error(request, 'Solo se pueden procesar pedidos pendientes.')
    
    return redirect('orders:detail', pk=order.pk)




@login_required
def order_mark_completed(request, pk):
    """Marcar pedido como completado"""
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    
    if order.status in ['pending', 'in_progress']:
        order.status = 'completed'
        order.save(update_fields=['status'])
        messages.success(request, f'Pedido {order.order_number} completado.')
    else:
        messages.error(request, 'No se puede completar este pedido.')
    
    return redirect('orders:detail', pk=order.pk)




@login_required
def order_cancel(request, pk):
    """Cancelar pedido"""
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    
    if order.status in ['pending', 'in_progress']:
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        messages.warning(request, f'Pedido {order.order_number} cancelado.')
    else:
        messages.error(request, 'No se puede cancelar este pedido.')
    
    return redirect('orders:detail', pk=order.pk)




@login_required
@transaction.atomic
def order_generate_sale(request, pk):
    """Generar venta desde un pedido completado con descuento automático de stock"""
    from sales.models import Sale, SaleItem
    from stock.models import StockMovement
    
    tenant = _require_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    
    # Validaciones
    if order.status != 'completed':
        messages.error(request, 'Solo se pueden generar ventas desde pedidos completados.')
        return redirect('orders:detail', pk=order.pk)
    
    if order.has_sale():
        messages.error(request, 'Este pedido ya tiene una venta generada.')
        return redirect('orders:detail', pk=order.pk)
    
    if order.items.count() == 0:
        messages.error(request, 'No se puede generar una venta sin ítems.')
        return redirect('orders:detail', pk=order.pk)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        currency = request.POST.get('currency', 'PYG') if payment_method == 'cash' else request.POST.get('currency_other', 'PYG')
        
        # Verificar stock disponible ANTES de crear la venta
        for order_item in order.items.all():
            product = order_item.product
            quantity_needed = int(order_item.quantity)
            
            if product.current_stock < quantity_needed:
                messages.error(
                    request, 
                    f'Stock insuficiente para {product.name}. '
                    f'Disponible: {product.current_stock}, Necesario: {quantity_needed}'
                )
                return redirect('orders:detail', pk=order.pk)
        
        # Calcular monto pagado y vuelto
        paid_amount = int(order.total)
        change_amount = 0
        
        if payment_method == 'cash':
            amount_received = int(request.POST.get('amount_received', 0))
            if amount_received < order.total:
                messages.error(request, 'El monto recibido es insuficiente.')
                return redirect('orders:generate_sale', pk=order.pk)
            paid_amount = amount_received
            change_amount = amount_received - int(order.total)
        
        # Crear la venta
        sale = Sale.objects.create(
            tenant=tenant,
            invoice_number=f'V-{timezone.now().strftime("%Y%m%d%H%M%S")}',
            customer=order.customer,
            order=order,
            total_amount=int(order.total),
            subtotal=int(order.subtotal),
            tax_amount=int(order.total_tax),
            payment_method=payment_method,
            currency_paid=currency,
            paid_amount=paid_amount if payment_method != 'credit' else 0,
            change_amount=change_amount,
            status='completed' if payment_method != 'credit' else 'pending',
            created_by=request.user,
        )
        
        # Copiar items del pedido a la venta Y descontar stock
        for order_item in order.items.all():
            product = order_item.product
            quantity_needed = int(order_item.quantity)
            
            # Crear el item de venta
            SaleItem.objects.create(
                tenant=tenant,
                sale=sale,
                product=product,
                quantity=quantity_needed,
                unit_price=int(order_item.unit_price),
                tax_type=order_item.tax_type,
                subtotal=int(order_item.total),
                tax_amount=int(order_item.tax_amount),
            )
            
            # Descontar del stock
            previous_stock = product.current_stock
            product.current_stock -= quantity_needed
            product.save(update_fields=['current_stock'])
            
            # Registrar el movimiento de stock para auditoría
            StockMovement.objects.create(
                tenant=tenant,
                product=product,
                movement_type='sale',
                quantity=-quantity_needed,  # Negativo = salida
                previous_stock=previous_stock,
                new_stock=product.current_stock,
                reference=f'Venta {sale.invoice_number} (Pedido {order.order_number})',
                notes=f'Descuento automático por venta desde pedido',
                created_by=request.user,
            )
        
        # Si es crédito, crear cuenta por cobrar
        if payment_method == 'credit':
            from customers.models import CustomerAccount
            installments = int(request.POST.get('installments', 1))
            
            # Crear la cuenta principal
            CustomerAccount.objects.create(
                tenant=tenant,
                customer=order.customer,
                transaction_type='sale',
                amount=order.total,
                balance=order.total,
                description=f'Venta {sale.invoice_number} - {installments} cuotas',
                sale=sale,
                total_installments=installments,
            )
        
        # Mensaje de éxito con información del vuelto si aplica
        success_msg = f'Venta {sale.invoice_number} generada exitosamente desde pedido {order.order_number}. Stock actualizado.'
        if change_amount > 0:
            success_msg += f' Vuelto: ₲ {change_amount:,.0f}'
        
        messages.success(request, success_msg)
        return redirect('sales:sale_detail', pk=sale.pk)
    
    # GET: Mostrar formulario
    return render(request, 'orders/generate_sale.html', {
        'tenant': tenant,
        'order': order,
    })
