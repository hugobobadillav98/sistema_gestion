from django.contrib import admin
from .models import Tenant, TenantUser, ExchangeRate


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'subscription_plan', 'is_active', 'created_at')
    list_filter = ('is_active', 'subscription_plan', 'created_at')
    search_fields = ('name', 'tax_id', 'email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'slug', 'is_active')
        }),
        ('Business Details', {
            'fields': ('tax_id', 'address', 'phone', 'email')
        }),
        ('Subscription', {
            'fields': ('subscription_plan', 'subscription_expires')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('user__username', 'user__email', 'tenant__name')
    raw_id_fields = ('user', 'tenant')


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['currency', 'get_currency_display', 'rate_to_pyg', 'updated_at']
    list_editable = ['rate_to_pyg']
    readonly_fields = ['updated_at']
    
    def get_currency_display(self, obj):
        return obj.get_currency_display()
    get_currency_display.short_description = 'Nombre'