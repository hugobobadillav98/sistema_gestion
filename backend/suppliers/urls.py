# suppliers/urls.py

from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Proveedores
    path('list/', views.supplier_list, name='list'),
    path('create/', views.supplier_create, name='create'),
    path('<uuid:supplier_id>/', views.supplier_detail, name='detail'),
    path('<uuid:supplier_id>/edit/', views.supplier_edit, name='edit'),  # ← NUEVO
    path('<uuid:supplier_id>/toggle-active/', views.supplier_toggle_active, name='toggle_active'),  # ← NUEVO
    
    # Compras
    path('purchase/create/', views.purchase_create, name='purchase_create'),
    
    # Pagos
    path('payment/create/', views.payment_create, name='payment_create'),
]
