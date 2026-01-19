from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Product, Category
from decimal import Decimal


@login_required
def product_list(request):
    """Lista de productos con búsqueda y filtros"""
    products = Product.objects.filter(tenant=request.tenant)
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(code__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Filtro por categoría
    category_id = request.GET.get('category', '')
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Filtro por stock bajo
    low_stock = request.GET.get('low_stock', '')
    if low_stock:
        products = products.filter(current_stock__lte=models.F('minimum_stock'))
    
    categories = Category.objects.filter(tenant=request.tenant, is_active=True)
    
    context = {
        'products': products,
        'categories': categories,
        'search': search,
        'selected_category': category_id,
    }
    return render(request, 'stock/product_list.html', context)


@login_required
def product_create(request):
    """Crear producto"""
    if request.method == 'POST':
        try:
            product = Product(
                tenant=request.tenant,
                code=request.POST.get('code'),
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                sale_price=Decimal(request.POST.get('sale_price', 0)),
                purchase_price=Decimal(request.POST.get('purchase_price', 0)),
                tax_type=request.POST.get('tax_type', '10'),
                current_stock=int(request.POST.get('current_stock', 0)),
                minimum_stock=int(request.POST.get('minimum_stock', 0)),
                is_active=request.POST.get('is_active') == 'on'
            )
            
            # Categoría (opcional)
            category_id = request.POST.get('category')
            if category_id:
                product.category_id = category_id
            
            product.save()
            messages.success(request, f'Producto "{product.name}" creado exitosamente.')
            return redirect('stock:product_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear producto: {str(e)}')
    
    categories = Category.objects.filter(tenant=request.tenant, is_active=True)
    context = {'categories': categories}
    return render(request, 'stock/product_form.html', context)


@login_required
def product_edit(request, pk):
    """Editar producto"""
    product = get_object_or_404(Product, pk=pk, tenant=request.tenant)
    
    if request.method == 'POST':
        try:
            product.code = request.POST.get('code')
            product.name = request.POST.get('name')
            product.description = request.POST.get('description', '')
            product.sale_price = Decimal(request.POST.get('sale_price', 0))
            product.purchase_price = Decimal(request.POST.get('purchase_price', 0))
            product.tax_type = request.POST.get('tax_type', '10')
            product.current_stock = int(request.POST.get('current_stock', 0))
            product.minimum_stock = int(request.POST.get('minimum_stock', 0))
            product.is_active = request.POST.get('is_active') == 'on'
            
            category_id = request.POST.get('category')
            product.category_id = category_id if category_id else None
            
            product.save()
            messages.success(request, f'Producto "{product.name}" actualizado.')
            return redirect('stock:product_list')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar: {str(e)}')
    
    categories = Category.objects.filter(tenant=request.tenant, is_active=True)
    context = {
        'product': product,
        'categories': categories,
        'is_edit': True
    }
    return render(request, 'stock/product_form.html', context)


@login_required
def product_delete(request, pk):
    """Eliminar producto"""
    product = get_object_or_404(Product, pk=pk, tenant=request.tenant)
    
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Producto "{name}" eliminado.')
        return redirect('stock:product_list')
    
    return render(request, 'stock/product_confirm_delete.html', {'product': product})

@login_required
def category_list(request):
    """Lista de categorías"""
    categories = Category.objects.filter(tenant=request.tenant)
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        categories = categories.filter(name__icontains=search)
    
    context = {'categories': categories, 'search': search}
    return render(request, 'stock/category_list.html', context)


@login_required
def category_create(request):
    """Crear categoría"""
    if request.method == 'POST':
        try:
            category = Category(
                tenant=request.tenant,
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                is_active=request.POST.get('is_active') == 'on'
            )
            category.save()
            messages.success(request, f'Categoría "{category.name}" creada exitosamente.')
            return redirect('stock:category_list')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'stock/category_form.html', {})


@login_required
def category_edit(request, pk):
    """Editar categoría"""
    category = get_object_or_404(Category, pk=pk, tenant=request.tenant)
    
    if request.method == 'POST':
        try:
            category.name = request.POST.get('name')
            category.description = request.POST.get('description', '')
            category.is_active = request.POST.get('is_active') == 'on'
            category.save()
            messages.success(request, f'Categoría "{category.name}" actualizada.')
            return redirect('stock:category_list')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    context = {'category': category, 'is_edit': True}
    return render(request, 'stock/category_form.html', context)


@login_required
def category_delete(request, pk):
    """Eliminar categoría"""
    category = get_object_or_404(Category, pk=pk, tenant=request.tenant)
    
    if request.method == 'POST':
        # Verificar si tiene productos asociados
        if category.products.exists():
            messages.error(request, 'No se puede eliminar. Tiene productos asociados.')
            return redirect('stock:category_list')
        
        name = category.name
        category.delete()
        messages.success(request, f'Categoría "{name}" eliminada.')
        return redirect('stock:category_list')
    
    return render(request, 'stock/category_confirm_delete.html', {'category': category})