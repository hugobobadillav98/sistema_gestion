from django.contrib import admin
from .models import Customer, CustomerPayment


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_id', 'phone', 'customer_type', 'current_balance', 'is_active')
    list_filter = ('customer_type', 'is_active', 'created_at')
    search_fields = ('name', 'tax_id', 'email', 'phone')
    readonly_fields = ('current_balance', 'created_at', 'updated_at')


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'amount', 'payment_method', 'payment_date', 'created_by')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('customer__name', 'reference')
    raw_id_fields = ('customer',)
