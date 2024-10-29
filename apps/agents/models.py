from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.common.utils import get_models
from pydantic import BaseModel
import os
import importlib
import logging
import uuid
import random
import json
from django.contrib.postgres.fields import ArrayField
from django.conf import settings
from apps.agents.utils import load_tool, get_tool_description

logger = logging.getLogger(__name__)

User = get_user_model()

AVATAR_CHOICES = [
    'user.jpg', 'team-5.jpg', 'team-4.jpg', 'team-3.jpg', 'team-2.jpg', 'kal-visuals-square.jpg',
    'team-1.jpg', 'marie.jpg', 'ivana-squares.jpg', 'ivana-square.jpg'
]

def random_avatar():
    return random.choice(AVATAR_CHOICES)

def get_available_tools():
    tools_dir = os.path.join('apps', 'agents', 'tools')
    available_tools = []

    for root, dirs, files in os.walk(tools_dir):
        for dir_name in dirs:
            if not dir_name.startswith('__'):  # Exclude directories like __pycache__
                tool_path = os.path.relpath(os.path.join(root, dir_name), tools_dir)
                available_tools.append(tool_path.replace(os.path.sep, '.'))

    return available_tools

def default_embedder():
    return {'provider': 'openai'}

def user_directory_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f'user_{instance.crew_execution.user.id}/{filename}'

class Tool(models.Model):
    tool_class = models.CharField(max_length=255)
    tool_subclass = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    module_path = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.module_path:
            self.module_path = f"apps.agents.tools.{self.tool_class}"
        
        try:
            tool = load_tool(self)
            if tool:
                self.name = getattr(tool, 'name', self.tool_subclass)
                self.description = get_tool_description(tool.__class__)
            else:
                raise ValueError(f"Failed to load tool: {self.module_path}.{self.tool_subclass}. Check the logs for more details.")
        except Exception as e:
            logger.error(f"Error in Tool.save: {str(e)}")
            raise ValidationError(f"Error loading tool: {str(e)}")

        super().save(*args, **kwargs)

class Agent(models.Model):
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=100)
    goal = models.TextField()
    backstory = models.TextField()
    llm = models.CharField(max_length=100, default=settings.GENERAL_MODEL)
    tools = models.ManyToManyField(Tool, blank=True)
    function_calling_llm = models.CharField(max_length=100, null=True, blank=True, default=settings.GENERAL_MODEL)
    max_iter = models.IntegerField(default=25)
    max_rpm = models.IntegerField(null=True, blank=True)
    max_execution_time = models.IntegerField(null=True, blank=True)
    verbose = models.BooleanField(default=False)
    allow_delegation = models.BooleanField(default=False)
    step_callback = models.CharField(max_length=255, null=True, blank=True)
    cache = models.BooleanField(default=True)
    system_template = models.TextField(null=True, blank=True)
    prompt_template = models.TextField(null=True, blank=True)
    response_template = models.TextField(null=True, blank=True)
    allow_code_execution = models.BooleanField(default=False)
    max_retry_limit = models.IntegerField(default=2)
    use_system_prompt = models.BooleanField(default=True)
    respect_context_window = models.BooleanField(default=True)
    avatar = models.CharField(max_length=100, default=random_avatar)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        available_models = get_models()
        if self.llm not in available_models:
            raise ValidationError({'llm': f"Selected LLM '{self.llm}' is not available. Please choose from: {', '.join(available_models)}"})

    def get_tool_settings(self, tool):
        """Get settings for a specific tool."""
        return self.tool_settings.filter(tool=tool).first()

    def get_forced_output_tools(self):
        """Get all tools that have force_output_as_result=True."""
        return self.tools.filter(
            id__in=self.tool_settings.filter(
                force_output_as_result=True
            ).values_list('tool_id', flat=True)
        )

    def has_force_output_enabled(self, tool):
        """Check if force output is enabled for a specific tool."""
        tool_setting = self.tool_settings.filter(tool=tool).first()
        return tool_setting.force_output_as_result if tool_setting else False

class Task(models.Model):
    description = models.TextField()
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True)
    expected_output = models.TextField()
    tools = models.ManyToManyField(Tool, blank=True)
    async_execution = models.BooleanField(default=False)
    context = models.ManyToManyField('self', symmetrical=False, blank=True)
    config = models.JSONField(null=True, blank=True)
    output_json = models.CharField(max_length=255, null=True, blank=True)
    output_pydantic = models.CharField(max_length=255, null=True, blank=True)
    output_file = models.CharField(max_length=255, null=True, blank=True)
    output = models.TextField(null=True, blank=True)
    callback = models.CharField(max_length=255, null=True, blank=True)
    human_input = models.BooleanField(default=False)
    converter_cls = models.CharField(max_length=255, null=True, blank=True)
    crew_execution = models.ForeignKey('CrewExecution', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.description[:50]

    def save_output_file(self, content):
        if self.output_file:
            file_name = os.path.basename(self.output_file)
        else:
            file_name = f"task_{self.id}_output.txt"
        
        file_path = user_directory_path(self, file_name)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w') as f:
            f.write(content)
        
        self.output_file = file_path
        self.save()

class Crew(models.Model):
    name = models.CharField(max_length=100)
    agents = models.ManyToManyField(Agent)
    tasks = models.ManyToManyField(Task, through='CrewTask')
    process = models.CharField(max_length=20, choices=[('sequential', 'Sequential'), ('hierarchical', 'Hierarchical')], default='sequential')
    verbose = models.BooleanField(default=False)
    manager_llm = models.CharField(max_length=100, null=True, blank=True, default=settings.GENERAL_MODEL)
    function_calling_llm = models.CharField(max_length=100, null=True, blank=True, default=settings.GENERAL_MODEL)
    config = models.JSONField(null=True, blank=True)
    max_rpm = models.IntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, default='English')
    language_file = models.CharField(max_length=255, null=True, blank=True)
    memory = models.BooleanField(default=False)
    cache = models.BooleanField(default=True)
    embedder = models.JSONField(default=default_embedder)
    full_output = models.BooleanField(default=False)
    share_crew = models.BooleanField(default=False)
    output_log_file = models.CharField(max_length=255, null=True, blank=True)
    manager_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_crews')
    manager_callbacks = models.JSONField(null=True, blank=True)
    prompt_file = models.CharField(max_length=255, null=True, blank=True)
    planning = models.BooleanField(default=False)
    planning_llm = models.CharField(max_length=100, null=True, blank=True, default=settings.GENERAL_MODEL)
    input_variables = ArrayField(
        models.CharField(max_length=100),
        blank=True,
        null=True,
        default=list
    )

    def __str__(self):
        return self.name

class CrewExecution(models.Model):
    crew = models.ForeignKey(Crew, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    client = models.ForeignKey('seo_manager.Client', on_delete=models.SET_NULL, null=True, blank=True)
    inputs = models.JSONField()
    outputs = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=25, choices=[
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('WAITING_FOR_HUMAN_INPUT', 'Waiting for Human Input'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ], default='PENDING')
    human_input_request = models.JSONField(null=True, blank=True)
    human_input_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.crew.name} - {self.created_at}"

    def save_task_output_file(self, task, content):
        task.crew_execution = self
        task.save_output_file(content)

class CrewMessage(models.Model):
    execution = models.ForeignKey(CrewExecution, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    agent = models.CharField(max_length=255, null=True, blank=True)  # Add this line

    def __str__(self):
        return f"Message for execution {self.execution.id} at {self.timestamp}"

class Pipeline(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='Idle')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def clean(self):
        # Validate that stages are properly structured
        stages = self.stages.all().order_by('order')
        for stage in stages:
            if stage.is_parallel:
                if stage.crew is not None:
                    raise ValidationError("Parallel stages should not have a single crew assigned.")
            else:
                if stage.crew is None:
                    raise ValidationError("Sequential stages must have a crew assigned.")

class PipelineStage(models.Model):
    pipeline = models.ForeignKey(Pipeline, related_name='stages', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    crew = models.ForeignKey('Crew', on_delete=models.SET_NULL, null=True, blank=True)
    order = models.PositiveIntegerField()
    is_parallel = models.BooleanField(default=False)
    is_router = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.pipeline.name} - {self.name}"

    def clean(self):
        if self.is_router and self.crew is not None:
            raise ValidationError("Router stages should not have a crew assigned.")

class PipelineRoute(models.Model):
    stage = models.ForeignKey(PipelineStage, related_name='routes', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    condition = models.TextField()  # This would store a serialized form of the condition
    target_pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.stage.name} - {self.name}"

class PipelineExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.pipeline.name} Execution - {self.created_at}"

class PipelineRunResult(models.Model):
    execution = models.ForeignKey(PipelineExecution, related_name='run_results', on_delete=models.CASCADE)
    raw_output = models.TextField(blank=True)
    json_output = models.JSONField(null=True, blank=True)
    pydantic_output = models.TextField(null=True, blank=True)  # This would store a serialized form of the Pydantic model
    token_usage = models.JSONField(null=True, blank=True)
    trace = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Run Result for {self.execution.pipeline.name}"

class CrewOutput(models.Model):
    execution = models.OneToOneField(CrewExecution, on_delete=models.CASCADE, related_name='crew_output')
    raw = models.TextField()
    pydantic = models.JSONField(null=True, blank=True)
    json_dict = models.JSONField(null=True, blank=True)
    token_usage = models.JSONField(null=True, blank=True)

    @property
    def json(self):
        return json.dumps(self.json_dict) if self.json_dict else None

    def to_dict(self):
        return self.json_dict or (self.pydantic.dict() if self.pydantic else None) or {}

    def __str__(self):
        if self.pydantic:
            return str(self.pydantic)
        elif self.json_dict:
            return json.dumps(self.json_dict)
        else:
            return self.raw

    def save(self, *args, **kwargs):
        # Convert UsageMetrics to a dictionary if it's not already
        if self.token_usage and hasattr(self.token_usage, 'dict'):
            self.token_usage = self.token_usage.dict()
        super().save(*args, **kwargs)

class CrewTask(models.Model):
    crew = models.ForeignKey(Crew, on_delete=models.CASCADE, related_name='crew_tasks')
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('crew', 'task')

    def __str__(self):
        return f"{self.crew.name} - {self.task.description} (Order: {self.order})"

class AgentToolSettings(models.Model):
    agent = models.ForeignKey('Agent', on_delete=models.CASCADE, related_name='tool_settings')
    tool = models.ForeignKey('Tool', on_delete=models.CASCADE)
    force_output_as_result = models.BooleanField(default=False)

    class Meta:
        unique_together = ('agent', 'tool')
