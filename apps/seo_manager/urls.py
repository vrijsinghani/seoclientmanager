from django.urls import path, include
from . import views, views_summarizer, views_analytics

app_name = 'seo_manager'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('summarize/', views_summarizer.summarize_view, name='summarize_view'),
    path('task_status/<str:task_id>/', views_summarizer.task_status, name='task_status'),
    path('clients/', include([
        path('', views.client_list, name='client_list'),
        path('add/', views.add_client, name='add_client'),
        path('<int:client_id>/', include([
            path('', views.client_detail, name='client_detail'),
            path('edit/', views.edit_client, name='edit_client'),
            path('delete/', views.delete_client, name='delete_client'),
            path('analytics/', views_analytics.client_analytics, name='client_analytics'),
            path('search-console/', views.client_search_console, name='client_search_console'),
            path('ads/', views.client_ads, name='client_ads'),
            path('dataforseo/', views.client_dataforseo, name='client_dataforseo'),
            path('credentials/', include([
                path('ga/oauth/add/', views.add_ga_credentials_oauth, name='add_ga_credentials_oauth'),
                path('ga/service-account/add/', views.add_ga_credentials_service_account, name='add_ga_credentials_service_account'),
                path('ga/remove/', views.remove_ga_credentials, name='remove_ga_credentials'),
                path('sc/add/', views.add_sc_credentials, name='add_sc_credentials'),
                path('sc/remove/', views.remove_sc_credentials, name='remove_sc_credentials'),
            ])),
            path('business-objective/', include([
                path('edit/<int:objective_index>/', views.edit_business_objective, name='edit_business_objective'),
                path('delete/<int:objective_index>/', views.delete_business_objective, name='delete_business_objective'),
            ])),
        ])),
    ])),
    path('summarize/', views_summarizer.summarize_view, name='summarize_view'),
    path('test/', views.test_view, name='test_view'),
    path('activity-log/', views.activity_log, name='activity_log'),
    path('client/<int:client_id>/create-meta-tags-snapshot/', views.create_meta_tags_snapshot, name='create_meta_tags_snapshot'),
    path('create-meta-tags-snapshot-url/', views.create_meta_tags_snapshot_url, name='create_meta_tags_snapshot_url'),
]
