from django.contrib import admin
from .models import Crew, CrewExecution, CrewMessage, Agent, Task, Tool
from .forms import AgentForm, TaskForm, CrewForm

@admin.register(Crew)
class CrewAdmin(admin.ModelAdmin):
    form = CrewForm
    list_display = ('name', 'process', 'verbose', 'memory', 'cache', 'full_output', 'share_crew', 'planning')
    list_filter = ('process', 'verbose', 'memory', 'cache', 'full_output', 'share_crew', 'planning')
    filter_horizontal = ('agents', 'tasks')
    search_fields = ('name', 'language', 'language_file', 'output_log_file', 'prompt_file')
    fieldsets = (
        (None, {
            'fields': ('name', 'agents', 'tasks', 'process')
        }),
        ('Language Model Settings', {
            'fields': ('manager_llm', 'function_calling_llm', 'planning_llm')
        }),
        ('Execution Settings', {
            'fields': ('verbose', 'max_rpm', 'memory', 'cache', 'full_output', 'planning')
        }),
        ('Language and Localization', {
            'fields': ('language', 'language_file')
        }),
        ('Callbacks and Logging', {
            'fields': ('step_callback', 'task_callback', 'output_log_file')
        }),
        ('Advanced Settings', {
            'classes': ('collapse',),
            'fields': ('config', 'embedder', 'share_crew', 'manager_agent', 'manager_callbacks', 'prompt_file'),
        }),
    )

@admin.register(CrewExecution)
class CrewExecutionAdmin(admin.ModelAdmin):
    list_display = ('crew', 'user', 'client', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('crew__name', 'user__username', 'client__name')

@admin.register(CrewMessage)
class CrewMessageAdmin(admin.ModelAdmin):
    list_display = ('execution', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('execution__crew__name', 'content')

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    form = AgentForm
    list_display = ('name', 'role', 'llm', 'function_calling_llm', 'verbose', 'allow_delegation', 'allow_code_execution')
    list_filter = ('verbose', 'allow_delegation', 'allow_code_execution', 'use_system_prompt', 'respect_context_window')
    search_fields = ('name', 'role', 'goal', 'backstory')
    filter_horizontal = ('tools',)
    fieldsets = (
        (None, {
            'fields': ('name', 'role', 'goal', 'backstory', 'llm', 'tools')
        }),
        ('Advanced options', {
            'classes': ('collapse',),
            'fields': ('function_calling_llm', 'max_iter', 'max_rpm', 'max_execution_time', 'verbose', 'allow_delegation', 'step_callback', 'cache', 'system_template', 'prompt_template', 'response_template', 'allow_code_execution', 'max_retry_limit', 'use_system_prompt', 'respect_context_window'),
        }),
    )

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = TaskForm
    list_display = ('description', 'agent', 'async_execution', 'human_input', 'output_type')
    list_filter = ('async_execution', 'human_input')
    filter_horizontal = ('tools', 'context')
    search_fields = ('description', 'agent__name', 'expected_output')
    readonly_fields = ('output',)

    def output_type(self, obj):
        if obj.output_json:
            return 'JSON'
        elif obj.output_pydantic:
            return 'Pydantic'
        elif obj.output_file:
            return 'File'
        else:
            return 'Default'
    output_type.short_description = 'Output Type'

    fieldsets = (
        (None, {
            'fields': ('description', 'agent', 'expected_output', 'tools', 'async_execution', 'context')
        }),
        ('Advanced options', {
            'classes': ('collapse',),
            'fields': ('config', 'output_json', 'output_pydantic', 'output_file', 'human_input', 'converter_cls'),
        }),
        ('Output', {
            'fields': ('output',),
        }),
    )

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description', 'function')
