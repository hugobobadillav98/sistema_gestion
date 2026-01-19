from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User
from core.models import TenantAwareModel, TenantManager
from customers.models import Customer
from stock.models import Product
from decimal import Decimal, ROUND_HALF_UP
import uuid


class Sale(TenantAwareModel):
    """
    Main sales transaction with multi-currency support.
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
    
    # Totales en Guaraníes (sin decimales) - SIEMPRE en PYG para contabilidad
    subtotal = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=0)
    
    # Multi-Currency Support
    CURRENCY_CHOICES = [
        ('PYG', 'Guaraníes (₲)'),
        ('USD', 'Dólares ($)'),
        ('BRL', 'Reales (R$)'),
    ]
    currency_paid = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='PYG',
        verbose_name="Moneda de Pago",
        help_text="Moneda en la que pagó el cliente"
    )
    
    # Monto pagado en moneda original (si pagó en USD o BRL)
    paid_amount_original = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Monto Original",
        help_text="Monto en la moneda que pagó el cliente"
    )
    
    # Tasas de cambio usadas en esta venta (histórico)
    exchange_rate_usd = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=7300,
        verbose_name="Tasa USD",
        help_text="1 USD = X PYG al momento de la venta"
    )
    exchange_rate_brl = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=1450,
        verbose_name="Tasa BRL",
        help_text="1 BRL = X PYG al momento de la venta"
    )
    
    # Payment Method (actualizado con PIX)
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Efectivo'),
        ('card', 'Tarjeta Débito/Crédito'),
        ('pix', 'PIX'),
        ('transfer', 'Transferencia Bancaria'),
        ('credit', 'Fiado/Crédito'),
        ('mixed', 'Pago Mixto'),
    ]
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash'
    )
    
    # Montos de pago (SIEMPRE en PYG)
    paid_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=0, 
        default=0,
        verbose_name="Monto Pagado (PYG)",
        help_text="Monto convertido a guaraníes"
    )
    change_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=0, 
        default=0,
        verbose_name="Vuelto (PYG)"
    )
    
    # PIX Reference (para pagos PIX)
    pix_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referencia PIX",
        help_text="ID de transacción PIX"
    )
    
    # Status
    STATUS_CHOICES = [
        ('completed', 'Completada'),
        ('pending', 'Pendiente'),
        ('cancelled', 'Cancelada'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='completed'
    )
    
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    # User who made the sale
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, 
        null=True,
        related_name='sales'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-sale_date']
        indexes = [
            models.Index(fields=['tenant', 'sale_date']),
            models.Index(fields=['tenant', 'invoice_number']),
            models.Index(fields=['tenant', 'currency_paid']),
            models.Index(fields=['tenant', 'payment_method']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - ₲{self.total_amount:,.0f}"
    
    @property
    def is_paid(self):
        """Check if sale is fully paid"""
        return self.paid_amount >= self.total_amount
    
    @property
    def outstanding_balance(self):
        """Calculate outstanding balance"""
        return max(0, self.total_amount - self.paid_amount)
    
    def get_paid_amount_display(self):
        """Return paid amount in original currency with symbol"""
        if self.currency_paid == 'PYG':
            return f"₲ {self.paid_amount:,.0f}"
        elif self.currency_paid == 'USD':
            return f"$ {self.paid_amount_original:,.2f} (₲ {self.paid_amount:,.0f})"
        elif self.currency_paid == 'BRL':
            return f"R$ {self.paid_amount_original:,.2f} (₲ {self.paid_amount:,.0f})"
        return f"₲ {self.paid_amount:,.0f}"
    
    def get_exchange_rate_used(self):
        """Return the exchange rate used for this sale"""
        if self.currency_paid == 'USD':
            return self.exchange_rate_usd
        elif self.currency_paid == 'BRL':
            return self.exchange_rate_brl
        return 1



class SaleItem(TenantAwareModel):
    """
    Individual items in a sale.
    """
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Guardar el tipo de IVA del momento de la venta
    tax_type = models.CharField(
        max_length=10, 
        choices=[
            ('EXENTA', 'Exenta'),
            ('5', 'Gravada 5%'),
            ('10', 'Gravada 10%'),
        ],
        default='10'
    )
    
    # Totales calculados
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=0)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Item de Venta"
        verbose_name_plural = "Items de Venta"
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def calculate_totals(self):
        """
        Calcular totales según sistema paraguayo:
        - Precio ya incluye IVA
        - Extraemos el IVA del precio final
        """
        # 1. Calcular subtotal bruto (precio x cantidad)
        gross_total = self.unit_price * self.quantity
        
        # 2. Aplicar descuento
        self.discount_amount = int((gross_total * self.discount_percent / 100).quantize(Decimal('1'), ROUND_HALF_UP))
        
        # 3. Subtotal después de descuento (CON IVA incluido)
        self.subtotal = gross_total - self.discount_amount
        
        # 4. Extraer el IVA que ya está incluido
        tax_rate = Decimal('0')
        if self.tax_type == '10':
            tax_rate = Decimal('0.10')
        elif self.tax_type == '5':
            tax_rate = Decimal('0.05')
        
        if tax_rate > 0:
            # Fórmula: precio_base = precio_con_iva / (1 + tasa)
            base_price = self.subtotal / (1 + tax_rate)
            self.tax_amount = int((self.subtotal - base_price).quantize(Decimal('1'), ROUND_HALF_UP))
        else:
            self.tax_amount = 0
        
        return self.subtotal
