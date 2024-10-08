from django.urls import path
from . import views
from . import views_admin

app_name = 'agents'

urlpatterns = [
    # Existing URLs
    path('', views.crew_list, name='crew_list'),
    path('crew/<int:crew_id>/', views.crew_detail, name='crew_detail'),
    path('executions/', views.execution_list, name='execution_list'),
    path('execution/<int:execution_id>/', views.execution_detail, name='execution_detail'),
    
    # Admin views
    path('manage/agents/', views_admin.manage_agents, name='manage_agents'),
    path('manage/agents/add/', views_admin.add_agent, name='add_agent'),
    path('manage/agents/edit/<int:agent_id>/', views_admin.edit_agent, name='edit_agent'),
    path('manage/agents/delete/<int:agent_id>/', views_admin.delete_agent, name='delete_agent'),
    
    path('manage/tasks/', views_admin.manage_tasks, name='manage_tasks'),
    path('manage/tasks/add/', views_admin.add_task, name='add_task'),
    path('manage/tasks/edit/<int:task_id>/', views_admin.edit_task, name='edit_task'),
    path('manage/tasks/delete/<int:task_id>/', views_admin.delete_task, name='delete_task'),
    
    path('manage/tools/', views_admin.manage_tools, name='manage_tools'),
    path('manage/tools/add/', views_admin.add_tool, name='add_tool'),
    path('manage/tools/edit/<int:tool_id>/', views_admin.edit_tool, name='edit_tool'),
    path('manage/tools/delete/<int:tool_id>/', views_admin.delete_tool, name='delete_tool'),
    path('get_tool_info/', views_admin.get_tool_info, name='get_tool_info'),  # New URL for fetching tool info

    # Crew management URLs
    path('manage/crews/', views_admin.manage_crews, name='manage_crews'),
    path('manage/crews/add/', views_admin.add_crew, name='add_crew'),
    path('manage/crews/edit/<int:crew_id>/', views_admin.edit_crew, name='edit_crew'),
    path('manage/crews/delete/<int:crew_id>/', views_admin.delete_crew, name='delete_crew'),
    
    # New URL for updating crew agents
    path('manage/crews/update_agents/<int:crew_id>/', views_admin.update_crew_agents, name='update_crew_agents'),
]