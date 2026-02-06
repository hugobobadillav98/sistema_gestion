# config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', core_views.dashboard_view, name='dashboard'),
    path('sales/', include('sales.urls')),
    path('stock/', include('stock.urls')),
    path('customers/', include('customers.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('users/', include('users.urls')),
    path('settings/', core_views.settings_view, name='settings'),
    path('settings/business/', core_views.business_settings, name='business_settings'),
    path('settings/exchange-rates/', core_views.exchange_rates, name='exchange_rates'),
    
    # Autenticación
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', core_views.logout_view, name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
