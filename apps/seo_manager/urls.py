from django.urls import path
from . import views

app_name = 'seo_manager'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('clients/', views.client_list, name='client_list'),
    path('client/<int:client_id>/', views.client_detail, name='client_detail'),
    path('client/<int:client_id>/analytics/', views.client_analytics, name='client_analytics'),
    path('client/<int:client_id>/search-console/', views.client_search_console, name='client_search_console'),
    path('client/<int:client_id>/ads/', views.client_ads, name='client_ads'),
    path('client/<int:client_id>/dataforseo/', views.client_dataforseo, name='client_dataforseo'),
    path('test/', views.test_view, name='test_view'),
    path('client/<int:client_id>/add-ga-credentials-oauth/', views.add_ga_credentials_oauth, name='add_ga_credentials_oauth'),
    path('client/<int:client_id>/add-ga-credentials-service-account/', views.add_ga_credentials_service_account, name='add_ga_credentials_service_account'),
    path('client/<int:client_id>/remove-ga-credentials/', views.remove_ga_credentials, name='remove_ga_credentials'),
    path('client/<int:client_id>/add-sc-credentials/', views.add_sc_credentials, name='add_sc_credentials'),
    path('client/<int:client_id>/remove-sc-credentials/', views.remove_sc_credentials, name='remove_sc_credentials'),
]
