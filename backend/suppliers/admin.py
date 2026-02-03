# suppliers/admin.py

from django.contrib import admin
from .models import Supplier, SupplierAccount

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'tax_id', 'phone', 'payment_terms_days', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'tax_id', 'email', 'phone']
    
@admin.register(SupplierAccount)
class SupplierAccountAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'transaction_type', 'amount', 'transaction_date', 'due_date', 'status']
    list_filter = ['transaction_type', 'transaction_date', 'due_date']
    search_fields = ['supplier__name', 'invoice_number', 'reference']
    
    def status(self, obj):
        return obj.status
    status.short_description = 'Estado'
