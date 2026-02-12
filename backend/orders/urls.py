from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.order_list, name='list'),
    path('<uuid:pk>/', views.order_detail, name='detail'),
    path('<uuid:pk>/in-progress/', views.order_mark_in_progress, name='mark_in_progress'),
    path('<uuid:pk>/completed/', views.order_mark_completed, name='mark_completed'),
    path('<uuid:pk>/cancel/', views.order_cancel, name='cancel'),
    path('<uuid:pk>/generate-sale/', views.order_generate_sale, name='generate_sale'),
]
