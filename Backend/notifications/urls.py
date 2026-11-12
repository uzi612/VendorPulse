from django.urls import path
from .views import notification_list_api, notification_mark_read_api, notification_read_all_api

urlpatterns = [
    path('', notification_list_api, name='notification_list'),
    path('read-all/', notification_read_all_api, name='notification_read_all'),
    path('<int:pk>/read/', notification_mark_read_api, name='notification_mark_read'),
]
