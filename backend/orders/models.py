# orders/models.py

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from core.models import TenantAwareModel
from customers.models import Customer
from stock.models import Product
from quotes.models import Quote
import uuid


class Order(TenantAwareModel):
    """Pedido/Orden de compra"""
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_progress', 'En Proceso'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField('Número de Pedido', max_length=20, unique=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='Cliente'
    )
    
    # Relación con presupuesto (si viene de uno)
    quote = models.ForeignKey(
        Quote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Presupuesto Origen'
    )
    
    # Fechas
    created_date = models.DateTimeField('Fecha Creación', auto_now_add=True)
    order_date = models.DateField('Fecha Pedido')
    expected_delivery = models.DateField('Fecha Entrega Esperada', null=True, blank=True)
    
    # Estado
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Totales
    subtotal = models.DecimalField(
        'Subtotal',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_tax = models.DecimalField(
        'Total IVA',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        'Total General',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Información adicional
    notes = models.TextField('Observaciones', blank=True)
    internal_notes = models.TextField('Notas Internas', blank=True)
    
    # Usuario que creó
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders_created',
        verbose_name='Creado por'
    )
    
    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.order_number} - {self.customer.name}"
    
    def calculate_totals(self):
        """Calcular y guardar totales del pedido"""
        items = self.items.all()
        
        self.subtotal = sum(item.base_amount for item in items)
        self.total_tax = sum(item.tax_amount for item in items)
        self.total = sum(item.total for item in items)
        self.save(update_fields=['subtotal', 'total_tax', 'total'])

    def has_sale(self):
        """Verificar si ya se generó una venta para este pedido"""
        return hasattr(self, 'sales') and self.sales.exists()

    def can_generate_sale(self):
        """Verificar si se puede generar una venta"""
        return self.status == 'completed' and not self.has_sale()


class OrderItem(models.Model):
    """Ítem del pedido"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Pedido'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name='Producto'
    )
    
    # Cantidad y precio
    quantity = models.DecimalField(
        'Cantidad',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    unit_price = models.DecimalField(
        'Precio Unitario (c/IVA)',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Datos de IVA
    tax_type = models.CharField(
        'Tipo IVA',
        max_length=10,
        choices=Product.TAX_CHOICES,
        default='10'
    )
    tax_rate = models.DecimalField(
        'IVA %',
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00')
    )
    
    # Totales
    base_amount = models.DecimalField(
        'Base imponible',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_amount = models.DecimalField(
        'Monto IVA',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        'Total (c/IVA)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    notes = models.TextField('Notas', blank=True)
    
    class Meta:
        verbose_name = 'Item de Pedido'
        verbose_name_plural = 'Items de Pedido'
        ordering = ['id']
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def _calc_tax_rate_decimal(self) -> Decimal:
        """Devuelve la tasa de IVA en decimal (0, 0.05, 0.10)"""
        return self.product.get_tax_rate() if self.product_id else Decimal('0')
    
    def recalculate_totals(self):
        """Calcula base, IVA y total"""
        qty = self.quantity or Decimal('0')
        price_with_tax = self.unit_price or Decimal('0')
        
        self.total = (qty * price_with_tax).quantize(Decimal('0.01'))
        
        rate = self._calc_tax_rate_decimal()
        self.tax_rate = self.product.get_tax_percentage() if self.product_id else Decimal('0')
        self.tax_type = self.product.tax_type if self.product_id else 'EXENTA'
        
        if rate == 0:
            self.base_amount = self.total
            self.tax_amount = Decimal('0.00')
        else:
            self.base_amount = (self.total / (Decimal('1') + rate)).quantize(Decimal('0.01'))
            self.tax_amount = (self.total - self.base_amount).quantize(Decimal('0.01'))
    
    def save(self, *args, **kwargs):
        self.recalculate_totals()
        super().save(*args, **kwargs)
        
        if self.order_id:
            self.order.calculate_totals()
    
    def delete(self, *args, **kwargs):
        """Al borrar un ítem, recalcular totales del pedido"""
        order = self.order
        super().delete(*args, **kwargs)
        
        if order:
            order.calculate_totals()
