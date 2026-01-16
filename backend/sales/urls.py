from django.urls import path
from . import views

app_name = 'sales' 

urlpatterns = [
    path('pos/', views.pos_view, name='pos'),
    path('create/', views.create_sale_view, name='create_sale'),
    path('list/', views.sales_list_view, name='sales_list'),
    path('<uuid:sale_id>/', views.sale_detail_view, name='sale_detail'),
    path('<uuid:sale_id>/cancel/', views.cancel_sale_view, name='cancel_sale'),
]
