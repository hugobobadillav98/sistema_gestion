from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from core.models import TenantUser
from .decorators import require_admin_role


def get_user_tenant(request):
    """Helper para obtener el tenant del usuario actual"""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    membership = request.user.tenant_memberships.filter(is_active=True).first()
    return membership.tenant if membership else None

@login_required
@require_admin_role  
def user_list(request):
    """Lista de usuarios del tenant"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    # Obtener TenantUsers del tenant
    tenant_users = TenantUser.objects.filter(
        tenant=tenant
    ).select_related('user').order_by('-is_active', 'user__username')
    
    context = {
        'tenant': tenant,
        'tenant_users': tenant_users,
    }
    return render(request, 'users/list.html', context)


@login_required
@require_admin_role  
def user_create(request):
    """Crear nuevo usuario"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        role = request.POST.get('role', 'seller')
        
        # Validaciones
        if not username or not password:
            messages.error(request, 'Usuario y contraseña son obligatorios.')
            return redirect('users:create')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya existe.')
            return redirect('users:create')
        
        try:
            with transaction.atomic():
                # Crear usuario
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                
                # Crear TenantUser
                TenantUser.objects.create(
                    tenant=tenant,
                    user=user,
                    role=role,
                    is_active=True
                )
                
                messages.success(request, f'Usuario "{username}" creado exitosamente.')
                return redirect('users:list')
                
        except Exception as e:
            messages.error(request, f'Error al crear usuario: {str(e)}')
            return redirect('users:create')
    
    context = {
        'tenant': tenant,
    }
    return render(request, 'users/create.html', context)


@login_required
@require_admin_role  
def user_edit(request, pk):
    """Editar usuario existente"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        user = tenant_user.user
        
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        tenant_user.role = request.POST.get('role', tenant_user.role)
        tenant_user.save()
        
        # Cambiar contraseña si se proporcionó
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
            user.save()
            messages.success(request, 'Contraseña actualizada.')
        
        messages.success(request, f'Usuario "{user.username}" actualizado.')
        return redirect('users:list')
    
    context = {
        'tenant': tenant,
        'tenant_user': tenant_user,
    }
    return render(request, 'users/edit.html', context)


@login_required
@require_admin_role  
def user_toggle_active(request, pk):
    """Activar/Desactivar usuario"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)
    
    # No permitir desactivarse a sí mismo
    if tenant_user.user == request.user:
        messages.error(request, 'No puede desactivar su propio usuario.')
        return redirect('users:list')
    
    tenant_user.is_active = not tenant_user.is_active
    tenant_user.save()
    
    status = 'activado' if tenant_user.is_active else 'desactivado'
    messages.success(request, f'Usuario "{tenant_user.user.username}" {status}.')
    
    return redirect('users:list')


@login_required
def user_list(request):
    """Lista de usuarios del tenant"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    # Obtener TenantUsers del tenant
    tenant_users = TenantUser.objects.filter(
        tenant=tenant
    ).select_related('user').order_by('-is_active', 'user__username')
    
    context = {
        'tenant': tenant,
        'tenant_users': tenant_users,
    }
    return render(request, 'users/list.html', context)


@login_required
def user_create(request):
    """Crear nuevo usuario"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        role = request.POST.get('role', 'seller')
        
        # Validaciones
        if not username or not password:
            messages.error(request, 'Usuario y contraseña son obligatorios.')
            return redirect('users:create')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya existe.')
            return redirect('users:create')
        
        try:
            with transaction.atomic():
                # Crear usuario
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                
                # Crear TenantUser
                TenantUser.objects.create(
                    tenant=tenant,
                    user=user,
                    role=role,
                    is_active=True
                )
                
                messages.success(request, f'Usuario "{username}" creado exitosamente.')
                return redirect('users:list')
                
        except Exception as e:
            messages.error(request, f'Error al crear usuario: {str(e)}')
            return redirect('users:create')
    
    context = {
        'tenant': tenant,
    }
    return render(request, 'users/create.html', context)


@login_required
def user_edit(request, pk):
    """Editar usuario existente"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        user = tenant_user.user
        
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        tenant_user.role = request.POST.get('role', tenant_user.role)
        tenant_user.save()
        
        # Cambiar contraseña si se proporcionó
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
            user.save()
            messages.success(request, 'Contraseña actualizada.')
        
        messages.success(request, f'Usuario "{user.username}" actualizado.')
        return redirect('users:list')
    
    context = {
        'tenant': tenant,
        'tenant_user': tenant_user,
    }
    return render(request, 'users/edit.html', context)


@login_required
def user_toggle_active(request, pk):
    """Activar/Desactivar usuario"""
    tenant = get_user_tenant(request)
    
    if not tenant:
        messages.error(request, 'No tiene un tenant asignado.')
        return redirect('dashboard')
    
    tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)
    
    # No permitir desactivarse a sí mismo
    if tenant_user.user == request.user:
        messages.error(request, 'No puede desactivar su propio usuario.')
        return redirect('users:list')
    
    tenant_user.is_active = not tenant_user.is_active
    tenant_user.save()
    
    status = 'activado' if tenant_user.is_active else 'desactivado'
    messages.success(request, f'Usuario "{tenant_user.user.username}" {status}.')
    
    return redirect('users:list')
