from django.db import models
from core.models import TenantAwareModel, TenantManager


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
