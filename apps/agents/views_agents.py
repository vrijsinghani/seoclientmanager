import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Agent
from .forms import AgentForm
import traceback
from django.conf import settings

logger = logging.getLogger(__name__)

def is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_admin)
def manage_agents(request):
    agents = Agent.objects.all()
    return render(request, 'agents/manage_agents.html', {'agents': agents})

@login_required
@user_passes_test(is_admin)
def add_agent(request):
    if request.method == 'POST':
        form = AgentForm(request.POST)
        if form.is_valid():
            try:
                agent = form.save(commit=False)
                agent.avatar = form.cleaned_data['avatar']
                agent.save()
                form.save_m2m()
                messages.success(request, 'Agent added successfully.')
                return redirect('agents:manage_agents')
            except Exception as e:
                messages.error(request, f"Error adding agent: {str(e)}")
    else:
        form = AgentForm(initial={
            'llm': settings.GENERAL_MODEL,
            'function_calling_llm': settings.GENERAL_MODEL
        })
    return render(request, 'agents/agent_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def edit_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    if request.method == 'POST':
        form = AgentForm(request.POST, instance=agent)
        if form.is_valid():
            try:
                agent = form.save(commit=False)
                agent.avatar = form.cleaned_data['avatar']
                agent.save()
                form.save_m2m()
                messages.success(request, 'Agent updated successfully.')
                return redirect('agents:manage_agents')
            except Exception as e:
                messages.error(request, f"Error updating agent: {str(e)}")
    else:
        form = AgentForm(instance=agent)
    return render(request, 'agents/agent_form.html', {'form': form, 'agent': agent})

@login_required
@user_passes_test(is_admin)
def delete_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    if request.method == 'POST':
        agent.delete()
        messages.success(request, 'Agent deleted successfully.')
        return redirect('agents:manage_agents')
    return render(request, 'agents/confirm_delete.html', {'object': agent, 'type': 'agent'})
