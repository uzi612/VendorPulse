from django.urls import path
from .views import *


urlpatterns = [
    # Authentication API / View endpoints
    path('register/', register_view, name='api_register'),
    path('login/', login_view, name='api_login'),
    path('logout/', logout_view, name='api_logout'),
    
    # Profile & Account Data endpoint
    path('profile/', user_profile_api, name='api_user_profile'),
]