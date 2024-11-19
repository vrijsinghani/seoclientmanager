from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from apps.agents.models import Agent
from apps.common.utils import get_models

class ChatView(LoginRequiredMixin, TemplateView):
    template_name = 'agents/chat.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all agents
        agents = Agent.objects.all().order_by('name')
        
        context.update({
            'agents': agents,
            'models': get_models(),
            'add_agent_url': reverse('agents:add'),  # URL to add agent page
            'segment': 'chat',
            'default_model': self.request.user.profile.default_model if hasattr(self.request.user, 'profile') else None,
        })
        return context 