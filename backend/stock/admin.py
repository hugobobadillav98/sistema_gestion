from django.contrib import admin
from .models import Category, Product, StockMovement


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'sale_price', 'current_stock', 'is_low_stock', 'is_active')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')
    
    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Low Stock'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'movement_type', 'quantity', 'previous_stock', 'new_stock', 'created_at')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('product__name', 'reference')
    readonly_fields = ('created_at',)
    raw_id_fields = ('product',)
