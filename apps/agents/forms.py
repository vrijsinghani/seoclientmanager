import random
from django import forms
from .models import CrewExecution, Agent, Task, Tool, Crew, get_available_tools, AVATAR_CHOICES
from apps.seo_manager.models import Client
from apps.common.utils import get_models
import json
import logging

logger = logging.getLogger(__name__)

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
        self.fields['inputs'].required = False

    def clean_inputs(self):
        inputs = self.cleaned_data.get('inputs')
        if inputs:
            try:
                return json.loads(inputs)
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON format in inputs field")
        return {}  # Return an empty dict if no inputs provided

class HumanInputForm(forms.Form):
    response = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=True)

class AgentForm(forms.ModelForm):
    avatar = forms.ChoiceField(
        choices=[(choice, choice) for choice in AVATAR_CHOICES],
        widget=forms.RadioSelect(),
        required=False
    )
    llm = forms.ChoiceField(
        choices=[(model, model) for model in get_models()],
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )
    tools = forms.ModelMultipleChoiceField(
        queryset=Tool.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Agent
        fields = '__all__'  # Include all fields from the model
        widgets = {
            'goal': forms.Textarea(attrs={'rows': 3}),
            'backstory': forms.Textarea(attrs={'rows': 3}),
            'system_template': forms.Textarea(attrs={'rows': 4}),
            'prompt_template': forms.Textarea(attrs={'rows': 4}),
            'response_template': forms.Textarea(attrs={'rows': 4}),
            'tools': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'llm': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if isinstance(self.fields[field].widget, forms.CheckboxInput):
                self.fields[field].widget.attrs['class'] = 'form-check-input'
            elif not isinstance(self.fields[field].widget, (forms.SelectMultiple, forms.RadioSelect)):
                self.fields[field].widget.attrs['class'] = 'form-control'

        # Ensure avatar choices are set
        self.fields['avatar'].choices = [(choice, choice) for choice in AVATAR_CHOICES]

    def clean(self):
        cleaned_data = super().clean()
        logger.debug(f"Cleaned form data: {cleaned_data}")
        return cleaned_data

    def save(self, commit=True):
        logger.debug(f"Saving form with data: {self.cleaned_data}")
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()
        logger.debug(f"Saved instance: {instance.__dict__}")
        return instance

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