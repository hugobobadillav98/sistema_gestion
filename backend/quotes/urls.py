from django.urls import path
from . import views

app_name = 'quotes'

urlpatterns = [
    path('', views.quote_list, name='list'),
    path('create/', views.quote_create, name='create'),
    path('<uuid:pk>/', views.quote_detail, name='detail'),
    path('<uuid:pk>/edit/', views.quote_edit, name='edit'),
    path('<uuid:pk>/send/', views.quote_send, name='send'),
    path('<uuid:pk>/approve/', views.quote_approve, name='approve'),
    path('<uuid:pk>/reject/', views.quote_reject, name='reject'),
    path('<uuid:pk>/convert-to-order/', views.quote_convert_to_order, name='convert_to_order'),
    path('<uuid:pk>/assign-customer/', views.quote_assign_customer, name='assign_customer'),
]
