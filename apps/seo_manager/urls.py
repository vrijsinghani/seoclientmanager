from django.urls import path, include
from . import views, views_summarizer, views_analytics
from .views import (
    KeywordListView, KeywordCreateView, KeywordUpdateView,
    ProjectListView, ProjectCreateView, ProjectDetailView
)

app_name = 'seo_manager'

urlpatterns = [
    # Main URLs
    path('', views.dashboard, name='dashboard'),
    path('summarize/', views_summarizer.summarize_view, name='summarize_view'),
    path('task_status/<str:task_id>/', views_summarizer.task_status, name='task_status'),
    
    # Client URLs
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
            
            # Keyword Management URLs
            path('keywords/', include([
                path('', KeywordListView.as_view(), name='keyword_list'),
                path('add/', KeywordCreateView.as_view(), name='keyword_create'),
                path('import/', views.keyword_import, name='keyword_import'),
                path('<int:pk>/edit/', KeywordUpdateView.as_view(), name='keyword_update'),
                path('<int:pk>/rankings/', views.ranking_import, name='ranking_import'),
            ])),
            
            # SEO Project URLs
            path('projects/', include([
                path('', ProjectListView.as_view(), name='project_list'),
                path('add/', ProjectCreateView.as_view(), name='project_create'),
                path('<int:pk>/', ProjectDetailView.as_view(), name='project_detail'),
                path('<int:project_id>/edit/', views.edit_project, name='edit_project'),
                path('<int:project_id>/delete/', views.delete_project, name='delete_project'),
            ])),
            
            # Credentials URLs
            path('credentials/', include([
                path('ga/oauth/add/', views.add_ga_credentials_oauth, name='add_ga_credentials_oauth'),
                path('ga/service-account/add/', views.add_ga_credentials_service_account, name='add_ga_credentials_service_account'),
                path('ga/remove/', views.remove_ga_credentials, name='remove_ga_credentials'),
                path('sc/add/', views.add_sc_credentials, name='add_sc_credentials'),
                path('sc/remove/', views.remove_sc_credentials, name='remove_sc_credentials'),
            ])),
            
            # Business Objective URLs
            path('business-objective/', include([
                path('edit/<int:objective_index>/', views.edit_business_objective, name='edit_business_objective'),
                path('delete/<int:objective_index>/', views.delete_business_objective, name='delete_business_objective'),
            ])),
            
            # Meta Tags URLs
            path('create-meta-tags-snapshot/', views.create_meta_tags_snapshot, name='create_meta_tags_snapshot'),
            
            # Add this inside the client_id patterns
            path('profile/update/', views.update_client_profile, name='update_client_profile'),
            path('clients/<int:client_id>/keywords/<int:keyword_id>/debug/', views.debug_keyword_data, name='debug_keyword_data'),
            path('rankings/', include([
                path('collect/', views.collect_rankings, name='collect_rankings'),
                path('report/', views.generate_report, name='generate_report'),
                path('backfill/', views.backfill_rankings, name='backfill_rankings'),
                path('manage/', views.ranking_data_management, name='ranking_data_management'),
                path('export-csv/', views.export_rankings_csv, name='export_rankings_csv'),
            ])),
        ])),
    ])),
    
    # Other URLs
    path('activity-log/', views.activity_log, name='activity_log'),
    path('create-meta-tags-snapshot-url/', views.create_meta_tags_snapshot_url, name='create_meta_tags_snapshot_url'),
]

