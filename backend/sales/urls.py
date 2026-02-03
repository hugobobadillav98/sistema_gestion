from django.urls import path
from . import views
from . import views_cash  # NUEVO


app_name = 'sales' 


urlpatterns = [
    path('pos/', views.pos, name='pos'),
    path('create/', views.create_sale, name='create_sale'),
    path('<uuid:pk>/', views.sale_detail, name='sale_detail'),
    path('', views.sales_list, name='sales_list'),
    
    # Cash register URLs
    path('cash/', views_cash.cash_register_status, name='cash_register_status'),
    path('cash/open/', views_cash.open_cash_register, name='open_cash_register'),
    path('cash/<uuid:pk>/close/', views_cash.close_cash_register, name='close_cash_register'),
    path('cash/<uuid:pk>/', views_cash.cash_register_detail, name='cash_register_detail'),
]
