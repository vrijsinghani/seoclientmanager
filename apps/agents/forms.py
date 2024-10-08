from django import forms
from .models import CrewExecution, Agent, Task, Tool, Crew, get_available_tools
from apps.seo_manager.models import Client
from apps.common.utils import get_models
import json

class CrewExecutionForm(forms.ModelForm):
    client = forms.ModelChoiceField(queryset=Client.objects.all(), required=False)

    class Meta:
        model = CrewExecution
        fields = ['crew', 'inputs', 'client']
        widgets = {
            'inputs': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inputs'].widget.attrs['placeholder'] = 'Enter inputs as JSON'

class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = ['name', 'role', 'goal', 'backstory', 'llm', 'tools', 'function_calling_llm', 'max_iter', 'max_rpm', 'max_execution_time', 'verbose', 'allow_delegation', 'step_callback', 'cache', 'system_template', 'prompt_template', 'response_template', 'allow_code_execution', 'max_retry_limit', 'use_system_prompt', 'respect_context_window']
        widgets = {
            'backstory': forms.Textarea(attrs={'rows': 4}),
            'tools': forms.CheckboxSelectMultiple(),
            'system_template': forms.Textarea(attrs={'rows': 4}),
            'prompt_template': forms.Textarea(attrs={'rows': 4}),
            'response_template': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        available_models = get_models()
        self.fields['llm'] = forms.ChoiceField(
            choices=[(model, model) for model in available_models],
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        self.fields['function_calling_llm'] = forms.ChoiceField(
            choices=[(model, model) for model in available_models],
            widget=forms.Select(attrs={'class': 'form-control'}),
            required=False
        )
        self.fields['max_iter'].widget.attrs['min'] = 1
        self.fields['max_rpm'].widget.attrs['min'] = 0
        self.fields['max_execution_time'].widget.attrs['min'] = 0
        self.fields['max_retry_limit'].widget.attrs['min'] = 0

class TaskForm(forms.ModelForm):
    config = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)

    class Meta:
        model = Task
        fields = ['description', 'agent', 'expected_output', 'tools', 'async_execution', 'context', 'config', 'output_json', 'output_pydantic', 'output_file', 'human_input', 'converter_cls']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'expected_output': forms.Textarea(attrs={'rows': 4}),
            'tools': forms.CheckboxSelectMultiple(),
            'context': forms.CheckboxSelectMultiple(),
            'output_json': forms.TextInput(),
            'output_pydantic': forms.TextInput(),
            'output_file': forms.TextInput(),
            'converter_cls': forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['config'].widget.attrs['placeholder'] = 'Enter config as JSON'
        if self.instance.config:
            self.initial['config'] = json.dumps(self.instance.config, indent=2)

    def clean_config(self):
        config = self.cleaned_data.get('config')
        if config:
            try:
                return json.loads(config)
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON format in config field")
        return None

class ToolForm(forms.ModelForm):
    class Meta:
        model = Tool
        fields = ['tool_class']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tool_class'] = forms.ChoiceField(
            choices=[(tool, tool) for tool in get_available_tools()],
            widget=forms.Select(attrs={'class': 'form-control'})
        )

class CrewForm(forms.ModelForm):
    config = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)
    manager_callbacks = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)

    class Meta:
        model = Crew
        fields = ['name', 'agents', 'tasks', 'process', 'verbose', 'manager_llm', 'function_calling_llm', 
                  'config', 'max_rpm', 'language', 'language_file', 'memory', 'cache', 'embedder', 
                  'full_output', 'step_callback', 'task_callback', 'share_crew', 'output_log_file', 
                  'manager_agent', 'manager_callbacks', 'prompt_file', 'planning', 'planning_llm']
        widgets = {
            'agents': forms.CheckboxSelectMultiple(),
            'tasks': forms.CheckboxSelectMultiple(),
            'embedder': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        available_models = get_models()
        self.fields['manager_llm'] = forms.ChoiceField(
            choices=[(model, model) for model in available_models],
            widget=forms.Select(attrs={'class': 'form-control'}),
            required=False
        )
        self.fields['function_calling_llm'] = forms.ChoiceField(
            choices=[(model, model) for model in available_models],
            widget=forms.Select(attrs={'class': 'form-control'}),
            required=False
        )
        self.fields['planning_llm'] = forms.ChoiceField(
            choices=[(model, model) for model in available_models],
            widget=forms.Select(attrs={'class': 'form-control'}),
            required=False
        )
        self.fields['max_rpm'].widget.attrs['min'] = 0
        self.fields['max_rpm'].widget.attrs['step'] = 1
        self.fields['config'].widget.attrs['placeholder'] = 'Enter config as JSON'
        self.fields['manager_callbacks'].widget.attrs['placeholder'] = 'Enter manager callbacks as JSON'
        self.fields['embedder'].widget.attrs['placeholder'] = 'Enter embedder configuration as JSON'

        if self.instance.config:
            self.initial['config'] = json.dumps(self.instance.config, indent=2)
        if self.instance.manager_callbacks:
            self.initial['manager_callbacks'] = json.dumps(self.instance.manager_callbacks, indent=2)
        if self.instance.embedder:
            self.initial['embedder'] = json.dumps(self.instance.embedder, indent=2)

    def clean_config(self):
        return self._clean_json_field('config')

    def clean_manager_callbacks(self):
        return self._clean_json_field('manager_callbacks')

    def clean_embedder(self):
        return self._clean_json_field('embedder')

    def _clean_json_field(self, field_name):
        data = self.cleaned_data.get(field_name)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                raise forms.ValidationError(f"Invalid JSON format in {field_name} field")
        return None