from django.contrib import admin
from django.urls import path, include
from apps.seo_manager import views as seo_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.seo_manager.urls')),
    path('google/login/callback/', seo_views.google_oauth_callback, name='google_oauth_callback'),
    path('file-manager/', include('apps.file_manager.urls')),  # Keep this line as is
]
