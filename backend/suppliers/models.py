# suppliers/models.py

import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from core.models import TenantAwareModel, TenantManager


class Supplier(TenantAwareModel):
    """Proveedor"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Información básica
    name = models.CharField(max_length=200, verbose_name="Nombre/Razón Social")
    tax_id = models.CharField(max_length=50, blank=True, verbose_name="RUC/CNPJ/CPF")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Teléfono")
    address = models.TextField(blank=True, verbose_name="Dirección")
    
    # Condiciones comerciales
    payment_terms_days = models.IntegerField(
        default=30, 
        verbose_name="Plazo de pago (días)",
        help_text="Días de plazo para pagar (ej: 30, 60, 90)"
    )
    credit_limit = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Límite de crédito"
    )
    
    # Información adicional
    contact_person = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name="Persona de contacto"
    )
    notes = models.TextField(blank=True, verbose_name="Notas")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='suppliers_created',
        verbose_name="Creado por"
    )
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['name']
        unique_together = [['tenant', 'tax_id']]  # RUC único por tenant
        indexes = [
            models.Index(fields=['tenant', 'name']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'tax_id']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_balance(self):
        """Saldo actual que debemos al proveedor"""
        purchases = self.supplieraccount_set.filter(
            transaction_type='purchase',
            installment_number__gt=0  # Solo cuotas activas, no padres
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        payments = self.supplieraccount_set.filter(
            transaction_type='payment'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        adjustments = self.supplieraccount_set.filter(
            transaction_type='adjustment'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return purchases - payments + adjustments
    
    def get_pending_balance(self):
        """Saldo pendiente (solo compras no pagadas)"""
        pending = self.supplieraccount_set.filter(
            transaction_type='purchase',
            paid_date__isnull=True,
            installment_number__gt=0
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return pending
    
    def has_overdue_debt(self):
        """Tiene deuda vencida?"""
        return self.supplieraccount_set.filter(
            transaction_type='purchase',
            due_date__lt=timezone.now().date(),
            paid_date__isnull=True,
            installment_number__gt=0
        ).exists()
    
    def get_overdue_amount(self):
        """Monto total vencido"""
        overdue = self.supplieraccount_set.filter(
            transaction_type='purchase',
            due_date__lt=timezone.now().date(),
            paid_date__isnull=True,
            installment_number__gt=0
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return overdue


class SupplierAccount(TenantAwareModel):
    """Movimientos de cuenta con proveedor (compras y pagos)"""
    
    TRANSACTION_TYPES = [
        ('purchase', 'Compra a Crédito'),
        ('payment', 'Pago a Proveedor'),
        ('adjustment', 'Ajuste'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Efectivo'),
        ('bank_transfer', 'Transferencia Bancaria'),
        ('check', 'Cheque'),
        ('pix', 'PIX'),
        ('card', 'Tarjeta'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.CASCADE, 
        verbose_name="Proveedor"
    )
    
    # Tipo de transacción
    transaction_type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPES,
        verbose_name="Tipo"
    )
    
    # Montos
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Monto"
    )
    
    # Fechas
    transaction_date = models.DateField(
        default=timezone.now,
        verbose_name="Fecha"
    )
    due_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Fecha de vencimiento"
    )
    paid_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Fecha de pago"
    )
    
    # Cuotas
    total_installments = models.IntegerField(
        default=1, 
        verbose_name="Total de cuotas"
    )
    installment_number = models.IntegerField(
        default=1, 
        verbose_name="Número de cuota",
        help_text="0 = transacción padre, >0 = cuota activa"
    )
    parent_transaction = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        related_name='installments',
        verbose_name="Transacción padre"
    )
    
    # Método de pago (para pagos)
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHODS, 
        blank=True,
        verbose_name="Método de pago"
    )
    
    # Referencia y documentación
    invoice_number = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Nº Factura"
    )
    reference = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name="Referencia"
    )
    notes = models.TextField(blank=True, verbose_name="Notas")
    
    # Relación con la compra (si es un pago)
    related_purchase = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='payments_received',
        verbose_name="Compra relacionada"
    )
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Creado por"
    )
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Cuenta de Proveedor"
        verbose_name_plural = "Cuentas de Proveedores"
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'supplier']),
            models.Index(fields=['tenant', 'transaction_type']),
            models.Index(fields=['tenant', 'due_date']),
            models.Index(fields=['supplier', 'paid_date']),
        ]
    
    def __str__(self):
        if self.is_installment:
            return f"{self.get_transaction_type_display()} - {self.supplier.name} - Cuota {self.installment_number}/{self.total_installments} - ₲{self.amount:,.0f}"
        return f"{self.get_transaction_type_display()} - {self.supplier.name} - ₲{self.amount:,.0f}"
    
    @property
    def is_overdue(self):
        """Está vencido?"""
        if self.transaction_type == 'purchase' and self.due_date and not self.paid_date:
            return self.due_date < timezone.now().date()
        return False
    
    @property
    def days_overdue(self):
        """Días de atraso"""
        if self.is_overdue:
            return (timezone.now().date() - self.due_date).days
        return 0
    
    @property
    def is_installment(self):
        """Es una cuota?"""
        return self.total_installments > 1
    
    @property
    def status(self):
        """Estado de la cuenta"""
        if self.transaction_type == 'payment':
            return 'paid'
        elif self.paid_date:
            return 'paid'
        elif self.is_overdue:
            return 'overdue'
        elif self.due_date and self.due_date <= timezone.now().date():
            return 'due_today'
        else:
            return 'pending'
    
    @property
    def status_display(self):
        """Estado en español"""
        statuses = {
            'paid': 'Pagado',
            'overdue': f'Vencido ({self.days_overdue} días)',
            'due_today': 'Vence hoy',
            'pending': 'Pendiente'
        }
        return statuses.get(self.status, 'Desconocido')


class PurchaseItem(TenantAwareModel):
    """Items/Productos de una compra a proveedor"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relación con la compra
    purchase = models.ForeignKey(
        SupplierAccount,
        on_delete=models.CASCADE,
        related_name='items',
        limit_choices_to={'transaction_type': 'purchase'},
        verbose_name="Compra"
    )
    
    # Producto comprado
    product = models.ForeignKey(
        'stock.Product',
        on_delete=models.PROTECT,
        related_name='purchase_items',
        verbose_name="Producto"
    )
    
    # Cantidades y precios
    quantity = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Cantidad"
    )
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Precio unitario"
    )
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name="Subtotal"
    )
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Item de Compra"
        verbose_name_plural = "Items de Compra"
        ordering = ['product__name']
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity} = ₲{self.subtotal:,.0f}"
    
    def save(self, *args, **kwargs):
        # Calcular subtotal automáticamente
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)
