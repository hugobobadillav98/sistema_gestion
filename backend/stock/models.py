from django.db import models
from core.models import TenantAwareModel, TenantManager


class Category(TenantAwareModel):
    """
    Product category.
    """
    name = models.CharField(max_length=100, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']
        unique_together = ('tenant', 'name')
    
    def __str__(self):
        return self.name


class Product(TenantAwareModel):
    """
    Product/Item for sale.
    """
    # Basic information
    code = models.CharField(max_length=50, verbose_name="Product Code")
    name = models.CharField(max_length=200, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Description")
    
    # Category
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products'
    )
    
    # Pricing
    cost_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Cost Price"
    )
    sale_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name="Sale Price"
    )
    wholesale_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Wholesale Price"
    )
    
    # Inventory
    current_stock = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Current Stock"
    )
    minimum_stock = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Minimum Stock Alert"
    )
    unit = models.CharField(
        max_length=20,
        choices=[
            ('unit', 'Unit'),
            ('kg', 'Kilogram'),
            ('liter', 'Liter'),
            ('box', 'Box'),
            ('bag', 'Bag'),
        ],
        default='unit'
    )
    
    # Tax
    tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00,
        verbose_name="Tax Rate (%)"
    )
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Active")
    track_inventory = models.BooleanField(default=True, verbose_name="Track Inventory")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['name']
        unique_together = ('tenant', 'code')
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'name']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def is_low_stock(self):
        """Check if product is below minimum stock"""
        return self.current_stock <= self.minimum_stock
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.cost_price > 0:
            return ((self.sale_price - self.cost_price) / self.cost_price) * 100
        return 0


class StockMovement(TenantAwareModel):
    """
    Track all stock movements (purchases, sales, adjustments).
    """
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='stock_movements'
    )
    
    movement_type = models.CharField(
        max_length=20,
        choices=[
            ('purchase', 'Purchase'),
            ('sale', 'Sale'),
            ('adjustment', 'Adjustment'),
            ('return', 'Return'),
        ]
    )
    
    quantity = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name="Quantity"
    )
    
    # Positive = increase stock, Negative = decrease stock
    previous_stock = models.DecimalField(max_digits=12, decimal_places=2)
    new_stock = models.DecimalField(max_digits=12, decimal_places=2)
    
    reference = models.CharField(max_length=100, blank=True, verbose_name="Reference")
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='stock_movements'
    )
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product.name} - {self.movement_type} ({self.quantity})"
