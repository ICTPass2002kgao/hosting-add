from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView 
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
 
urlpatterns = [ # Use `str` for name
    path('logout/',  views.user_logout, name='logout'), 
    path('upload/', views.upload_certificate, name='upload_certificate'),
    path('<str:certificate_name>/', views.view_certificate, name='view_certificate'),
    path('',  views.superuser_login, name='login'),
    
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




