from django.utils.deprecation import MiddlewareMixin
from .models import TenantUser


class TenantMiddleware(MiddlewareMixin):
    """
    Adds current tenant to request based on logged user.
    """
    def process_request(self, request):
        request.tenant = None
        request.tenant_user = None
        
        if request.user.is_authenticated:
            # Get the first active tenant for this user
            # In the future, we can add tenant selection UI
            tenant_membership = TenantUser.objects.filter(
                user=request.user,
                is_active=True,
                tenant__is_active=True
            ).select_related('tenant').first()
            
            if tenant_membership:
                request.tenant = tenant_membership.tenant
                request.tenant_user = tenant_membership
