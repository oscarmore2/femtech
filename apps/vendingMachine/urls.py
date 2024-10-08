from django.urls import path
from .views import user_login, product_list1, product_list2, product_list3, detail, payment


urlpatterns = [
    path('login/', user_login, name='login'),
    path('products1/', product_list1, name='product-list1'),
    path('products2/', product_list2, name='product-list2'),
    path('products3/', product_list3, name='product-list3'),
    path('detail/', detail, name='detail'),
    path('payment/', payment, name='payment'),
]