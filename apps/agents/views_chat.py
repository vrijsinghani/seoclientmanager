from django.views.generic import TemplateView
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from apps.agents.models import Agent
from apps.common.utils import get_models
from django.conf import settings
from apps.seo_manager.models import Client
import logging

logger = logging.getLogger(__name__)

class ChatView(LoginRequiredMixin, TemplateView):
    template_name = 'agents/chat.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            # Get all agents
            agents = Agent.objects.all().order_by('name')
            logger.info(f"Found {agents.count()} agents")
            
            # Get all clients
            clients = Client.objects.all().order_by('name')
            logger.info(f"Found {clients.count()} clients")
            
            # Get models list
            models = get_models()
            logger.info(f"Found {len(models)} models")
            
            # Get default model
            default_model = settings.GENERAL_MODEL
            logger.info(f"Using default model: {default_model}")
            
            context.update({
                'agents': agents,
                'clients': clients,
                'models': models,
                'add_agent_url': reverse('agents:add_agent'),
                'segment': 'chat',
                'default_model': default_model,
            })
            logger.info("Context prepared successfully")
            
        except Exception as e:
            logger.error(f"Error preparing chat view context: {str(e)}", exc_info=True)
            raise
            
        return context