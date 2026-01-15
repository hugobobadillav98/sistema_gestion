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
def pos_view(request):
    """
    Point of Sale interface.
    """
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    # Get active products
    products = Product.objects.filter(
        tenant=request.tenant,
        is_active=True
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
    ).order_by('name')[:50]  # Limit for performance
    
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
    
    context = {
        'products': products[:50],  # Limit for performance
        'categories': categories,
        'customers': customers,
        'search': search,
    }
    
    return render(request, 'sales/pos.html', context)


@login_required
def create_sale_view(request):
    """
    Process sale creation from POS.
    """
    if request.method != 'POST':
        return redirect('pos')
    
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    try:
        # Get form data
        customer_id = request.POST.get('customer_id')
        payment_method = request.POST.get('payment_method', 'cash')
        paid_amount = Decimal(request.POST.get('paid_amount', '0'))
        notes = request.POST.get('notes', '')
        
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
        
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i]:
                items_data.append({
                    'product_id': product_ids[i],
                    'quantity': quantities[i],
                    'unit_price': unit_prices[i] if i < len(unit_prices) else None,
                    'discount_percent': discounts[i] if i < len(discounts) else 0,
                })
        
        if not items_data:
            messages.error(request, "No items in sale")
            return redirect('pos')
        
        # Create sale using service
        sale = SaleService.create_sale(
            tenant=request.tenant,
            items_data=items_data,
            customer=customer,
            payment_method=payment_method,
            paid_amount=paid_amount,
            created_by=request.user,
            notes=notes
        )
        
        messages.success(request, f"Sale {sale.invoice_number} created successfully!")
        return redirect('sale_detail', sale_id=sale.id)
        
    except Exception as e:
        messages.error(request, f"Error creating sale: {str(e)}")
        return redirect('pos')


@login_required
def sale_detail_view(request, sale_id):
    """
    View sale details and print receipt.
    """
    sale = get_object_or_404(
        Sale.objects.select_related('customer', 'created_by').prefetch_related('items__product'),
        id=sale_id,
        tenant=request.tenant
    )
    
    context = {
        'sale': sale,
    }
    
    return render(request, 'sales/sale_detail.html', context)


@login_required
def sales_list_view(request):
    """
    List all sales with filters.
    """
    if not request.tenant:
        messages.error(request, "No tenant assigned")
        return redirect('admin:index')
    
    sales = Sale.objects.filter(
        tenant=request.tenant
    ).select_related('customer', 'created_by').order_by('-sale_date')
    
    # Date filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        sales = sales.filter(sale_date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__lte=date_to)
    
    # Status filter
    status = request.GET.get('status')
    if status:
        sales = sales.filter(status=status)
    
    # Customer filter
    customer_id = request.GET.get('customer')
    if customer_id:
        sales = sales.filter(customer_id=customer_id)
    
    # Calculate totals
    totals = sales.aggregate(
        total_sales=Sum('total_amount'),
        total_count=Count('id')
    )
    
    context = {
        'sales': sales[:100],  # Paginate in production
        'totals': totals,
    }
    
    return render(request, 'sales/sales_list.html', context)


@login_required
def cancel_sale_view(request, sale_id):
    """
    Cancel a sale.
    """
    if request.method != 'POST':
        return redirect('sales_list')
    
    sale = get_object_or_404(Sale, id=sale_id, tenant=request.tenant)
    
    try:
        SaleService.cancel_sale(sale, cancelled_by=request.user)
        messages.success(request, f"Sale {sale.invoice_number} cancelled successfully")
    except Exception as e:
        messages.error(request, f"Error cancelling sale: {str(e)}")
    
    return redirect('sale_detail', sale_id=sale.id)
