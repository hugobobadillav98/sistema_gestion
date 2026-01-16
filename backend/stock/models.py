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


class Product(TenantAwareModel):  # Heredar de TenantAwareModel
    """Product model with Paraguay tax support"""
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    # Precios (CON IVA incluido - estándar Paraguay)
    sale_price = models.DecimalField(max_digits=10, decimal_places=0, help_text="Precio con IVA incluido")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    
    # Tipo de IVA (Paraguay)
    TAX_CHOICES = [
        ('EXENTA', 'Exenta (0%)'),
        ('5', 'Gravada 5%'),
        ('10', 'Gravada 10%'),
    ]
    tax_type = models.CharField(max_length=10, choices=TAX_CHOICES, default='10', help_text="Tipo de IVA")
    
    # Stock
    current_stock = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Métodos para cálculo de IVA (Paraguay)
    def get_tax_rate(self):
        """Retorna la tasa de IVA como decimal"""
        rates = {'EXENTA': Decimal('0'), '5': Decimal('0.05'), '10': Decimal('0.10')}
        return rates.get(self.tax_type, Decimal('0.10'))
    
    def get_base_price(self):
        """Calcula precio base (sin IVA) desde precio con IVA"""
        tax_rate = self.get_tax_rate()
        if tax_rate == 0:
            return self.sale_price
        return (self.sale_price / (1 + tax_rate)).quantize(Decimal('1'))
    
    def get_tax_amount(self):
        """Calcula el monto del IVA"""
        return (self.sale_price - self.get_base_price()).quantize(Decimal('1'))
    
    def get_tax_percentage(self):
        """Retorna el porcentaje como número entero"""
        rates = {'EXENTA': 0, '5': 5, '10': 10}
        return rates.get(self.tax_type, 10)

    class Meta:
        db_table = 'stock_product'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        unique_together = [['tenant', 'code']]  # Código único por tenant
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"


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
