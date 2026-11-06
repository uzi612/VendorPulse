from django.urls import path
from .views import *

urlpatterns = [
    path('register/', register_view, name='api_register'),
    path('login/', login_view, name='api_login'),
    path('logout/', logout_view, name='api_logout'),
    path('me/', me_view, name='api_me'),
]