from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView 
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
 
urlpatterns = [ # Use `str` for name
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'), 
    path('upload/', views.upload_certificate, name='upload_certificate'),
    path('<str:certificate_name>/', views.view_certificate, name='view_certificate'),
    path('', auth_views.LoginView.as_view(template_name='index.html'), name='login'),
    
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




