# users/decorators.py

from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def get_user_tenant(request):
    """Helper para obtener el tenant del usuario actual"""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    membership = request.user.tenant_memberships.filter(is_active=True).first()
    return membership.tenant if membership else None


def require_admin_role(view_func):
    """
    Decorador que verifica que el usuario tenga rol de admin u owner
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = get_user_tenant(request)
        
        if not tenant:
            messages.error(request, 'No tiene un tenant asignado.')
            return redirect('dashboard')
        
        # Verificar rol del usuario
        tenant_user = request.user.tenant_memberships.filter(
            tenant=tenant,
            is_active=True
        ).first()
        
        if not tenant_user or tenant_user.role not in ['owner', 'admin']:
            messages.error(request, 'No tiene permisos para acceder a esta sección.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
