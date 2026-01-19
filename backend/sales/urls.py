from django.urls import path
from . import views

app_name = 'sales' 

urlpatterns = [
    path('pos/', views.pos, name='pos'),
    path('create/', views.create_sale, name='create_sale'),
    path('<uuid:pk>/', views.sale_detail, name='sale_detail'),
    path('', views.sales_list, name='sale_list'),
]
