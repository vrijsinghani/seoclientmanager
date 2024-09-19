from django.contrib import admin
from django.urls import path, include
from apps.seo_manager import views as seo_views  # Add this import

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.seo_manager.urls')),
    # Change this line to directly use the view function
    path('google/login/callback/', seo_views.google_oauth_callback, name='google_oauth_callback'),
]