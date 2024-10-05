from django import forms
from .models import Client

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'website_url', 'status', 'group', 'target_audience']
        widgets = {
            'target_audience': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class BusinessObjectiveForm(forms.Form):
    goal = forms.CharField(max_length=255, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Goal',
        'style': 'width: 300px;'  # Adjust this value as needed
    }))
    metric = forms.CharField(max_length=255, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Metric',
        'style': 'width: 200px;'  # Adjust this value as needed
    }))
    target_date = forms.DateField(widget=forms.DateInput(attrs={
        'class': 'form-control',
        'type': 'date'
    }))
    status = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input'
    }))