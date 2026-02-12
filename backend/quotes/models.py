# quotes/models.py


from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from core.models import TenantAwareModel
from customers.models import Customer
from stock.models import Product
import uuid



class Quote(TenantAwareModel):
    """Presupuesto/Cotización"""
    
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('expired', 'Vencido'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote_number = models.CharField('Número de Presupuesto', max_length=20, unique=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='quotes',
        verbose_name='Cliente',
        null=True,
        blank=True  
    )
    
    # Fechas
    created_date = models.DateTimeField('Fecha Creación', auto_now_add=True)
    issue_date = models.DateField('Fecha Emisión')
    valid_until = models.DateField('Válido Hasta')
    
    # Estado
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
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
    
    # Conversión
    converted_to_order = models.BooleanField('Convertido a Pedido', default=False)
    converted_date = models.DateTimeField('Fecha Conversión', null=True, blank=True)
    
    # Usuario que creó
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='quotes_created',
        verbose_name='Creado por'
    )
    
    class Meta:
        verbose_name = 'Presupuesto'
        verbose_name_plural = 'Presupuestos'
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.quote_number} - {self.customer.name}"
    
    def calculate_totals(self):
        """Calcular y guardar totales del presupuesto"""
        items = self.items.all()
        
        self.subtotal = sum(item.base_amount for item in items)
        self.total_tax = sum(item.tax_amount for item in items)
        self.total = sum(item.total for item in items)
        self.save(update_fields=['subtotal', 'total_tax', 'total'])
    
    def can_be_edited(self):
        """Verificar si el presupuesto puede ser editado"""
        return self.status in ['draft', 'sent']
    
    def can_be_approved(self):
        """Verificar si el presupuesto puede ser aprobado"""
        return self.status == 'sent' and not self.converted_to_order



class QuoteItem(models.Model):
    """Ítem del presupuesto (precios con IVA incluido, estilo Paraguay)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Presupuesto'
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
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Precio de venta con IVA incluido; se puede ajustar manualmente.'
    )

    # Datos de IVA guardados en el ítem (para no depender de futuros cambios en el producto)
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
    base_amount = models.DecimalField(  # sin IVA
        'Base imponible',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_amount = models.DecimalField(   # monto de IVA
        'Monto IVA',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total = models.DecimalField(        # con IVA
        'Total (c/IVA)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    notes = models.TextField('Notas', blank=True)

    class Meta:
        verbose_name = 'Item de Presupuesto'
        verbose_name_plural = 'Items de Presupuesto'
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def _calc_tax_rate_decimal(self) -> Decimal:
        """Devuelve la tasa de IVA en decimal (0, 0.05, 0.10) según tax_type."""
        return self.product.get_tax_rate() if self.product_id else Decimal('0')

    def recalculate_totals(self):
        """
        Calcula base, IVA y total.
        unit_price y total están con IVA incluido (como en Paraguay).
        """
        qty = self.quantity or Decimal('0')
        price_with_tax = self.unit_price or Decimal('0')

        # total con IVA
        self.total = (qty * price_with_tax).quantize(Decimal('0.01'))

        # tasa de IVA (0, 0.05, 0.10)
        rate = self._calc_tax_rate_decimal()
        self.tax_rate = self.product.get_tax_percentage() if self.product_id else Decimal('0')
        self.tax_type = self.product.tax_type if self.product_id else 'EXENTA'

        if rate == 0:
            self.base_amount = self.total
            self.tax_amount = Decimal('0.00')
        else:
            # total = base * (1 + rate)  =>  base = total / (1 + rate)
            self.base_amount = (self.total / (Decimal('1') + rate)).quantize(Decimal('0.01'))
            self.tax_amount = (self.total - self.base_amount).quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        # Si no trae precio, usar el del producto
        if self.product_id and (self.unit_price is None or self.unit_price == 0):
            self.unit_price = self.product.default_unit_price_for_quotes

        # Recalcular totales del ítem
        self.recalculate_totals()
        super().save(*args, **kwargs)

        # Actualizar totales del presupuesto
        if self.quote_id:
            self.quote.calculate_totals()

    def delete(self, *args, **kwargs):
        """Al borrar un ítem, recalcular totales del presupuesto."""
        quote = self.quote
        super().delete(*args, **kwargs)
        
        # Recalcular totales después de borrar
        if quote:
            quote.calculate_totals()
