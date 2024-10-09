from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.common.utils import get_models
from pydantic import BaseModel
import os
import importlib
import logging
import uuid

logger = logging.getLogger(__name__)

User = get_user_model()

def get_available_tools():
    tools_dir = os.path.join('apps', 'agents', 'tools')
    return [name for name in os.listdir(tools_dir) if os.path.isdir(os.path.join(tools_dir, name))]

def default_embedder():
    return {'provider': 'openai'}

class Tool(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    tool_class = models.CharField(max_length=100, choices=[(tool, tool) for tool in get_available_tools()])
    schema = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        try:
            # Import the tool module
            module_path = f"apps.agents.tools.{self.tool_class}.{self.tool_class}"
            module = importlib.import_module(module_path)
            logger.info(f"Successfully imported module: {module_path}")

            # Get all classes defined in the module
            classes = [cls for name, cls in module.__dict__.items() if isinstance(cls, type)]
            logger.info(f"Found {len(classes)} classes in the module")

            # Try to find the correct tool class
            tool_class = next((cls for cls in classes if cls.__name__.lower() == self.tool_class.lower() or cls.__name__.endswith('Tool')), None)

            if tool_class is None:
                raise ValueError(f"Could not find a suitable Tool class in module {module_path}")

            logger.info(f"Using tool class: {tool_class.__name__}")

            # Set name and description
            self.name = getattr(tool_class, 'name', self.tool_class)
            self.description = getattr(tool_class, 'description', '')

            # Set schema if args_schema is available and is a subclass of BaseModel
            args_schema = getattr(tool_class, 'args_schema', None)
            if args_schema and issubclass(args_schema, BaseModel):
                self.schema = args_schema.schema()
            else:
                self.schema = None
                logger.warning(f"args_schema not found or not a subclass of BaseModel for {self.tool_class}")

        except Exception as e:
            logger.error(f"Error in Tool.save: {str(e)}")
            raise

        super().save(*args, **kwargs)

class Agent(models.Model):
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=100)
    goal = models.TextField()
    backstory = models.TextField()
    llm = models.CharField(max_length=100, default="gpt-3.5-turbo")
    tools = models.ManyToManyField(Tool, blank=True)
    function_calling_llm = models.CharField(max_length=100, null=True, blank=True)
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

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        available_models = get_models()
        if self.llm not in available_models:
            raise ValidationError({'llm': f"Selected LLM '{self.llm}' is not available. Please choose from: {', '.join(available_models)}"})

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

    def __str__(self):
        return self.description[:50]

class Crew(models.Model):
    name = models.CharField(max_length=100)
    agents = models.ManyToManyField(Agent)
    tasks = models.ManyToManyField(Task)
    process = models.CharField(max_length=20, choices=[('sequential', 'Sequential'), ('hierarchical', 'Hierarchical')], default='sequential')
    verbose = models.BooleanField(default=False)
    manager_llm = models.CharField(max_length=100, null=True, blank=True)
    function_calling_llm = models.CharField(max_length=100, null=True, blank=True)
    config = models.JSONField(null=True, blank=True)
    max_rpm = models.IntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, default='English')
    language_file = models.CharField(max_length=255, null=True, blank=True)
    memory = models.BooleanField(default=False)
    cache = models.BooleanField(default=True)
    embedder = models.JSONField(default=default_embedder)
    full_output = models.BooleanField(default=False)
    step_callback = models.CharField(max_length=255, null=True, blank=True)
    task_callback = models.CharField(max_length=255, null=True, blank=True)
    share_crew = models.BooleanField(default=False)
    output_log_file = models.CharField(max_length=255, null=True, blank=True)
    manager_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_crews')
    manager_callbacks = models.JSONField(null=True, blank=True)
    prompt_file = models.CharField(max_length=255, null=True, blank=True)
    planning = models.BooleanField(default=False)
    planning_llm = models.CharField(max_length=100, null=True, blank=True)

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

class CrewMessage(models.Model):
    execution = models.ForeignKey(CrewExecution, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.execution.crew.name} - {self.timestamp}"

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
    run_result = models.ForeignKey(PipelineRunResult, related_name='crew_outputs', on_delete=models.CASCADE)
    crew = models.ForeignKey('Crew', on_delete=models.CASCADE)
    output = models.TextField()

    def __str__(self):
        return f"Output from {self.crew.name} in {self.run_result.execution.pipeline.name}"