from django.db import models


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
