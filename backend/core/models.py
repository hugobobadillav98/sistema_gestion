from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

class TenantManager(models.Manager):
    """
    Custom manager that filters queryset by current tenant.
    """
    def __init__(self, *args, **kwargs):
        self.tenant_field = kwargs.pop('tenant_field', 'tenant')
        super().__init__(*args, **kwargs)
    
    def get_queryset(self):
        """Override to add tenant filtering if available"""
        return super().get_queryset()
    
    def for_tenant(self, tenant):
        """Filter queryset by specific tenant"""
        return self.get_queryset().filter(**{self.tenant_field: tenant})

class Tenant(models.Model):
    """
    Represents a business/company using the system.
    Each tenant is isolated from others.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name="Business Name")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    
    # Business information
    tax_id = models.CharField(max_length=50, blank=True, verbose_name="Tax ID/RUC")
    address = models.TextField(blank=True, verbose_name="Address")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Phone")
    email = models.EmailField(blank=True, verbose_name="Email")
    
    # Subscription info
    is_active = models.BooleanField(default=True, verbose_name="Active")
    subscription_plan = models.CharField(
        max_length=20,
        choices=[
            ('trial', 'Trial'),
            ('basic', 'Basic'),
            ('premium', 'Premium'),
        ],
        default='trial'
    )
    subscription_expires = models.DateField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class TenantUser(models.Model):
    """
    Links users to tenants with specific roles.
    A user can belong to multiple tenants.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_memberships')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='members')
    
    role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Owner'),
            ('admin', 'Administrator'),
            ('seller', 'Seller'),
            ('viewer', 'Viewer'),
        ],
        default='seller'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Tenant User"
        verbose_name_plural = "Tenant Users"
        unique_together = ('user', 'tenant')
    
    def __str__(self):
        return f"{self.user.username} - {self.tenant.name} ({self.role})"


class TenantAwareModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    
    class Meta:
        abstract = True

class ExchangeRate(models.Model):
    """Tasas de cambio para múltiples monedas"""
    CURRENCY_CHOICES = [
        ('PYG', 'Guaraní paraguayo'),
        ('USD', 'Dólar estadounidense'),
        ('BRL', 'Real brasileño'),
    ]
    
    currency = models.CharField(
        max_length=3, 
        unique=True, 
        choices=CURRENCY_CHOICES,
        verbose_name="Moneda"
    )
    rate_to_pyg = models.DecimalField(
        max_digits=12, 
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0001'))],
        help_text="¿Cuántos guaraníes equivale 1 unidad de esta moneda?",
        verbose_name="Tasa a Guaraníes"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    
    class Meta:
        verbose_name = "Tasa de Cambio"
        verbose_name_plural = "Tasas de Cambio"
        ordering = ['currency']
    
    def __str__(self):
        return f"1 {self.get_currency_display()} = ₲{self.rate_to_pyg:,.2f}"