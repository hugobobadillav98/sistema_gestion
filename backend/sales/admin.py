from django.contrib import admin
from .models import Sale, SaleItem
from customers.models import Customer, CustomerPayment


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['discount_amount', 'subtotal', 'tax_amount']
    fields = ['product', 'quantity', 'unit_price', 'discount_percent', 'tax_type', 'discount_amount', 'subtotal', 'tax_amount']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer', 'sale_date', 'total_amount', 'payment_method', 'status', 'created_by']
    list_filter = ['status', 'payment_method', 'sale_date']
    search_fields = ['invoice_number', 'customer__name']
    readonly_fields = ['invoice_number', 'subtotal', 'tax_amount', 'discount_amount', 'total_amount', 'sale_date', 'created_at', 'updated_at']
    inlines = [SaleItemInline]
    
    fieldsets = (
        ('Información General', {
            'fields': ('invoice_number', 'customer', 'sale_date', 'status')
        }),
        ('Totales', {
            'fields': ('subtotal', 'tax_amount', 'discount_amount', 'total_amount')
        }),
        ('Pago', {
            'fields': ('payment_method', 'paid_amount', 'change_amount')
        }),
        ('Adicional', {
            'fields': ('notes', 'created_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'discount_percent', 'subtotal', 'tax_amount']
    list_filter = ['tax_type']
    search_fields = ['sale__invoice_number', 'product__name']
    readonly_fields = ['discount_amount', 'subtotal', 'tax_amount']
