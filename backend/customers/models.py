from django.db import models
from core.models import TenantAwareModel, TenantManager
import uuid
from django.db.models import Sum
from django.utils import timezone


class Customer(TenantAwareModel):
    """
    Customer/Client model with account balance support.
    """
    # Basic information
    name = models.CharField(max_length=200, verbose_name="Name")
    tax_id = models.CharField(max_length=50, blank=True, verbose_name="Tax ID/RUC/CI")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Phone")
    mobile = models.CharField(max_length=50, blank=True, verbose_name="Mobile")
    
    # Address
    address = models.TextField(blank=True, verbose_name="Address")
    city = models.CharField(max_length=100, blank=True, verbose_name="City")
    
    # NUEVOS CAMPOS PARA FACTURACIÓN PARAGUAY
    ruc = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        verbose_name="RUC",
        help_text="Registro Único del Contribuyente"
    )
    dv = models.CharField(
        max_length=2, 
        blank=True, 
        null=True,
        verbose_name="DV",
        help_text="Dígito Verificador"
    )
    razon_social = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Razón Social",
        help_text="Nombre legal para facturación (si es empresa)"
    )
    requires_invoice = models.BooleanField(
        default=False,
        verbose_name="Requiere Factura Legal",
        help_text="Cliente solicita factura con RUC"
    )
    
    # Account information
    customer_type = models.CharField(
        max_length=20,
        choices=[
            ('retail', 'Retail/Minorista'),
            ('wholesale', 'Wholesale/Mayorista'),
        ],
        default='retail'
    )
    credit_limit = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Credit Limit"
    )
    current_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Current Balance"
    )
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Active")
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'name']),
            models.Index(fields=['tenant', 'tax_id']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def has_debt(self):
        """Check if customer has outstanding balance"""
        return self.current_balance > 0
    
    @property
    def available_credit(self):
        """Calculate available credit"""
        return self.credit_limit - self.current_balance
    
    # NUEVOS MÉTODOS
    def get_full_ruc(self):
        """Retorna RUC completo con DV"""
        if self.ruc and self.dv:
            return f"{self.ruc}-{self.dv}"
        return self.ruc or "Sin RUC"
    
    def can_invoice(self):
        """Verifica si el cliente puede recibir factura legal"""
        return self.requires_invoice and self.ruc
    
    def get_invoice_name(self):
        """Retorna el nombre para usar en factura"""
        return self.razon_social if self.razon_social else self.name
    
    def get_balance(self):
        """Get current balance (total debt - payments)."""
        balance = self.account_transactions.aggregate(
            total=Sum('amount')
        )['total'] or 0
        return balance

    def get_overdue_balance(self):
        """Get overdue balance."""
        overdue = self.account_transactions.filter(
            transaction_type='sale',
            due_date__lt=timezone.now().date()
        ).aggregate(total=Sum('amount'))['total'] or 0
        return overdue


class CustomerPayment(TenantAwareModel):
    """
    Payment made by customer to reduce balance.
    """
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Amount")
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('cash', 'Cash'),
            ('card', 'Debit/Credit Card'),
            ('transfer', 'Bank Transfer'),
            ('check', 'Check'),
        ],
        default='cash'
    )
    
    reference = models.CharField(max_length=100, blank=True, verbose_name="Reference")
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    payment_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='customer_payments'
    )
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Customer Payment"
        verbose_name_plural = "Customer Payments"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.customer.name} - {self.amount}"

class CustomerAccount(models.Model):
    """Customer credit account and payments."""
    
    TRANSACTION_TYPES = [
        ('sale', 'Venta a Crédito'),
        ('payment', 'Pago'),
        ('adjustment', 'Ajuste'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='account_transactions')
    
    # Transaction info
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=0)  # Positivo = debe, Negativo = pago
    
    # Reference
    sale = models.ForeignKey('sales.Sale', on_delete=models.CASCADE, null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text="N° de recibo, comprobante, etc")
    
    # Payment details
    payment_method = models.CharField(max_length=20, blank=True)
    
    # Dates
    transaction_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True, help_text="Fecha de vencimiento original")
    promised_date = models.DateField(null=True, blank=True, help_text="Fecha prometida de pago por el cliente")
    
    # Installments (Cuotas)
    total_installments = models.IntegerField(default=1, help_text="Número total de cuotas")
    installment_number = models.IntegerField(default=1, help_text="Número de esta cuota (1, 2, 3...)")
    parent_transaction = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='installments', 
        help_text="Transacción padre si esta es una cuota"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    class Meta:
        ordering = ['-transaction_date']
        
    def __str__(self):
        if self.total_installments > 1:
            return f"{self.customer.name} - {self.get_transaction_type_display()} - ₲{self.amount} ({self.installment_number}/{self.total_installments})"
        return f"{self.customer.name} - {self.get_transaction_type_display()} - ₲{self.amount}"
    
    @property
    def is_overdue(self):
        """Check if transaction is overdue based on promised date or due date."""
        from django.utils import timezone
        if self.transaction_type == 'sale':
            # Usar fecha prometida si existe, sino la fecha de vencimiento
            check_date = self.promised_date or self.due_date
            if check_date:
                return check_date < timezone.now().date()
        return False

    @property
    def days_overdue(self):
        """Get number of days overdue based on promised date or due date."""
        from django.utils import timezone
        if self.is_overdue:
            check_date = self.promised_date or self.due_date
            return (timezone.now().date() - check_date).days
        return 0
    
    @property
    def effective_due_date(self):
        """Get the effective due date (promised date takes priority)."""
        return self.promised_date or self.due_date
    
    @property
    def is_installment(self):
        """Check if this is an installment payment."""
        return self.total_installments > 1


def get_overdue_customers(tenant):
    """Get customers with overdue payments."""
    from django.db.models import Sum, Q
    from django.utils import timezone
    from decimal import Decimal
    
    # Obtener el balance por cliente considerando ventas y pagos
    customers_with_balance = CustomerAccount.objects.filter(
        tenant=tenant
    ).values('customer').annotate(
        total_sales=Sum('amount', filter=Q(transaction_type='sale')),
        total_payments=Sum('amount', filter=Q(transaction_type='payment'))
    )
    
    # Filtrar clientes con ventas vencidas
    overdue_customer_ids = []
    
    for customer_data in customers_with_balance:
        total_sales = customer_data['total_sales'] or Decimal('0')
        total_payments = customer_data['total_payments'] or Decimal('0')
        balance = total_sales - total_payments
        
        if balance > 0:
            # Verificar si tiene transacciones vencidas
            has_overdue = CustomerAccount.objects.filter(
                tenant=tenant,
                customer_id=customer_data['customer'],
                transaction_type='sale',
                due_date__lt=timezone.now().date()
            ).exists()
            
            if has_overdue:
                overdue_customer_ids.append(customer_data['customer'])
    
    return Customer.objects.filter(id__in=overdue_customer_ids)
