from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('subtotal', 'tax_amount', 'total')
    raw_id_fields = ('product',)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'total_amount', 'payment_method', 'status', 'sale_date')
    list_filter = ('status', 'payment_method', 'sale_date')
    search_fields = ('invoice_number', 'customer__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [SaleItemInline]
    raw_id_fields = ('customer',)
