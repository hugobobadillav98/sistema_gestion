from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import Sale, SaleItem
from .services import SaleService
from stock.models import Product, Category
from customers.models import Customer


@login_required
def pos(request):
    """
    Point of Sale interface.
    """
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    # Get active products with stock
    products = Product.objects.filter(
        tenant=request.tenant,
        is_active=True,
        current_stock__gt=0  # Solo productos con stock
    ).select_related('category').order_by('name')
    
    # Get categories for filtering
    categories = Category.objects.filter(
        tenant=request.tenant,
        is_active=True
    )
    
    # Get customers for quick selection
    customers = Customer.objects.filter(
        tenant=request.tenant,
        is_active=True
    ).order_by('name')[:50]
    
    # Search filter
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(code__icontains=search)
        )
    
    # Category filter
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Tasas de cambio (hardcoded por ahora)
    exchange_rates = {
        'PYG': 1,
        'USD': 7300,
        'BRL': 1450
    }
    
    context = {
        'products': products,
        'categories': categories,
        'customers': customers,
        'search': search,
        'exchange_rates': exchange_rates,
    }
    
    return render(request, 'sales/pos.html', context)



@login_required
def create_sale(request):
    """
    Process sale creation from POS.
    """
    if request.method != 'POST':
        return redirect('sales:pos')
    
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    try:
        # ========== DEBUG ==========
        print("=" * 50)
        print("POST DATA RECIBIDO:")
        for key, value in request.POST.items():
            print(f"{key}: {value}")
        print("=" * 50)
        # ===========================
        
        # Get multi-currency data
        customer_id = request.POST.get('customer_id')
        payment_method = request.POST.get('payment_method', 'cash')
        currency_paid = request.POST.get('currency_paid', 'PYG')
        paid_amount_original = Decimal(request.POST.get('paid_amount_original', '0'))
        exchange_rate_usd = Decimal(request.POST.get('exchange_rate_usd', '7300'))
        exchange_rate_brl = Decimal(request.POST.get('exchange_rate_brl', '1450'))
        pix_reference = request.POST.get('pix_reference', '')
        notes = request.POST.get('notes', '')
        
        # Calculate paid amount in PYG
        if currency_paid == 'PYG':
            paid_amount = paid_amount_original
        elif currency_paid == 'USD':
            paid_amount = paid_amount_original * exchange_rate_usd
        elif currency_paid == 'BRL':
            paid_amount = paid_amount_original * exchange_rate_brl
        else:
            paid_amount = paid_amount_original
        
        print(f"Currency: {currency_paid}, Paid Original: {paid_amount_original}, Paid PYG: {paid_amount}")
        
        # Get customer if provided
        customer = None
        if customer_id:
            customer = Customer.objects.get(id=customer_id, tenant=request.tenant)
        
        # Parse items from POST data
        items_data = []
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        unit_prices = request.POST.getlist('unit_price[]')
        discounts = request.POST.getlist('discount[]')
        
        print(f"Products: {len(product_ids)}, Quantities: {quantities}")
        
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i]:
                items_data.append({
                    'product_id': product_ids[i],
                    'quantity': int(quantities[i]),
                    'unit_price': Decimal(unit_prices[i]) if i < len(unit_prices) else None,
                    'discount_percent': Decimal(discounts[i]) if i < len(discounts) else 0,
                })
        
        if not items_data:
            messages.error(request, "No items in sale")
            return redirect('sales:pos')
        
        print(f"Items data: {items_data}")
        
        # Create sale using service
        sale = SaleService.create_sale(
            tenant=request.tenant,
            items_data=items_data,
            customer=customer,
            payment_method=payment_method,
            paid_amount=int(paid_amount),
            created_by=request.user,
            notes=notes,
            currency_paid=currency_paid,
            paid_amount_original=paid_amount_original,
            exchange_rate_usd=exchange_rate_usd,
            exchange_rate_brl=exchange_rate_brl,
            pix_reference=pix_reference
        )
        
        print(f"✅ Sale created: {sale.id} - {sale.invoice_number}")
        
        messages.success(request, f"Venta {sale.invoice_number} registrada exitosamente!")
        return redirect('sales:sale_detail', pk=sale.pk)
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al crear venta: {str(e)}")
        return redirect('sales:pos')


@login_required
def sale_detail(request, pk):
    """
    View sale details and print receipt.
    """
    sale = get_object_or_404(
        Sale.objects.select_related('customer', 'created_by').prefetch_related('items__product'),
        id=pk,  # ← Cambiar sale_id por pk
        tenant=request.tenant
    )
    
    context = {
        'sale': sale,
    }
    
    return render(request, 'sales/sale_detail.html', context)


@login_required
def sales_list(request):
    """
    List all sales with filters.
    """
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    sales = Sale.objects.filter(
        tenant=request.tenant
    ).select_related('customer', 'created_by').order_by('-sale_date')
    
    # Search by invoice number
    search = request.GET.get('search')
    if search:
        sales = sales.filter(invoice_number__icontains=search)
    
    # Date filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        sales = sales.filter(sale_date__gte=date_from)
    if date_to:
        # Incluir todo el día hasta las 23:59:59
        from datetime import datetime, timedelta
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
        date_to_end = date_to_obj + timedelta(days=1)
        sales = sales.filter(sale_date__lt=date_to_end)
    
    # Status filter
    status = request.GET.get('status')
    if status:
        sales = sales.filter(status=status)
    
    # Payment method filter
    payment_method = request.GET.get('payment_method')
    if payment_method:
        sales = sales.filter(payment_method=payment_method)
    
    # Calculate totals (solo para las ventas filtradas)
    totals = sales.aggregate(
        total_sales=Sum('total_amount'),
        total_count=Count('id')
    )
    
    context = {
        'sales': sales[:100],  # Limitar a 100 resultados
        'totals': totals,
        'search': search,
        'selected_status': status,
        'selected_payment': payment_method,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'sales/sales_list.html', context)



@login_required
def cancel_sale_view(request, sale_id):
    """
    Cancel a sale.
    """
    if request.method != 'POST':
        return redirect('sales:sales_list')  # ← CAMBIAR: agregar namespace
    
    sale = get_object_or_404(Sale, id=pk, tenant=request.tenant)  # ← CAMBIAR: sale_id → pk
    
    try:
        SaleService.cancel_sale(sale, cancelled_by=request.user)
        messages.success(request, f"Sale {sale.invoice_number} cancelled successfully")
    except Exception as e:
        messages.error(request, f"Error cancelling sale: {str(e)}")
    
    return redirect('sales:sale_detail', pk=pk)  # ← CAMBIAR: sale_id=sale.id → pk=pk