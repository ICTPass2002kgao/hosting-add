from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView 
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('',  views.superuser_login, name='login'),
    path('upload/', views.upload_certificate, name='upload_certificate'),
    
    # MOVED UP: Specific paths must come BEFORE the catch-all path
    path('logout/',  views.user_logout, name='logout'), 

    # LAST: This catches anything else (like UUIDs)
    path('<str:certificate_name>/', views.view_certificate, name='view_certificate'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)