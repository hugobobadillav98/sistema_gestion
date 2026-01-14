from django.db import models
from django.db.models import Sum
from core.models import TenantAwareModel, TenantManager
from customers.models import Customer
from stock.models import Product
import uuid


class Sale(TenantAwareModel):
    """
    Main sales transaction.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Invoice/Receipt number
    invoice_number = models.CharField(max_length=50, verbose_name="Invoice Number")
    
    # Customer
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.PROTECT,
        related_name='sales',
        null=True,
        blank=True
    )
    
    # Sale details
    sale_date = models.DateTimeField(auto_now_add=True)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('cash', 'Cash'),
            ('card', 'Debit/Credit Card'),
            ('transfer', 'Bank Transfer'),
            ('credit', 'On Credit'),
            ('mixed', 'Mixed'),
        ],
        default='cash'
    )
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('completed', 'Completed'),
            ('pending', 'Pending'),
            ('cancelled', 'Cancelled'),
        ],
        default='completed'
    )
    
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    # User who made the sale
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='sales'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Sale"
        verbose_name_plural = "Sales"
        ordering = ['-sale_date']
        indexes = [
            models.Index(fields=['tenant', 'sale_date']),
            models.Index(fields=['tenant', 'invoice_number']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.total_amount}"
    
    @property
    def is_paid(self):
        """Check if sale is fully paid"""
        return self.paid_amount >= self.total_amount
    
    @property
    def outstanding_balance(self):
        """Calculate outstanding balance"""
        return max(0, self.total_amount - self.paid_amount)


class SaleItem(TenantAwareModel):
    """
    Individual items in a sale.
    """
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Sale Item"
        verbose_name_plural = "Sale Items"
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def calculate_totals(self):
        """Calculate item totals"""
        # Subtotal after discount
        discount_amount = (self.unit_price * self.quantity) * (self.discount_percent / 100)
        self.subtotal = (self.unit_price * self.quantity) - discount_amount
        
        # Tax
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        
        # Total
        self.total = self.subtotal + self.tax_amount
