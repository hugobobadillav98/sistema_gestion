from django.urls import path
from . import views
from . import views_accounts 

app_name = 'customers'

urlpatterns = [
    # Accounts URLs PRIMERO (más específicas) - CAMBIAR uuid a int
    path('accounts/', views_accounts.accounts_list, name='accounts_list'),
    path('accounts/<int:pk>/', views_accounts.customer_account_detail, name='customer_account_detail'),
    path('accounts/<int:pk>/payment/', views_accounts.register_payment, name='register_payment'),
    
    # Customer URLs
    path('', views.customer_list, name='customer_list'),
    path('create/', views.customer_create, name='customer_create'),
    path('<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('<int:pk>/delete/', views.customer_delete, name='customer_delete'),
]