from django.contrib import admin
from .models import Customer, CustomerPayment


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'ruc', 'phone', 'city', 'customer_type', 'requires_invoice', 'is_active']
    list_filter = ['customer_type', 'requires_invoice', 'is_active', 'city']
    search_fields = ['name', 'ruc', 'tax_id', 'phone', 'email']
    readonly_fields = ['current_balance', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'customer_type', 'is_active')
        }),
        ('Datos Fiscales', {
            'fields': ('tax_id', 'ruc', 'dv', 'razon_social', 'requires_invoice')
        }),
        ('Contacto', {
            'fields': ('email', 'phone', 'mobile', 'address', 'city')
        }),
        ('Crédito', {
            'fields': ('credit_limit', 'current_balance')
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount', 'payment_method', 'payment_date', 'created_by']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['customer__name', 'reference']
    readonly_fields = ['payment_date']
