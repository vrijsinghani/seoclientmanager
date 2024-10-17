# This file was previously named views_admin.py
# The content remains the same, but you might want to remove any unused imports

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Crew, CrewTask
from .forms import CrewForm
import json

logger = logging.getLogger(__name__)

def is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_admin)
def manage_crews(request):
    crews = Crew.objects.all().prefetch_related('agents', 'tasks')
    context = {
        'crews': crews,
        'show_process': True,
        'show_planning': True,
        'show_language': True,
    }
    return render(request, 'agents/manage_crews.html', context)

@login_required
@user_passes_test(is_admin)
def add_crew(request):
    if request.method == 'POST':
        form = CrewForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Crew added successfully.')
            return redirect('agents:manage_crews')
    else:
        form = CrewForm()
    return render(request, 'agents/crew_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def edit_crew(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)
    if request.method == 'POST':
        form = CrewForm(request.POST, instance=crew)
        if form.is_valid():
            form.save()
            messages.success(request, 'Crew updated successfully.')
            return redirect('agents:manage_crews')
    else:
        form = CrewForm(instance=crew)
    return render(request, 'agents/crew_form.html', {'form': form, 'crew': crew})

@login_required
@user_passes_test(is_admin)
def delete_crew(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)
    if request.method == 'POST':
        crew.delete()
        messages.success(request, 'Crew deleted successfully.')
        return redirect('agents:manage_crews')
    return render(request, 'agents/confirm_delete.html', {'object': crew, 'type': 'crew'})

@login_required
@user_passes_test(is_admin)
def update_crew_agents(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)
    if request.method == 'POST':
        agent_ids = request.POST.getlist('agents')
        crew.agents.set(agent_ids)
        
        # Update manager_agent if it's in the POST data
        manager_agent_id = request.POST.get('manager_agent')
        if manager_agent_id:
            crew.manager_agent_id = manager_agent_id
        else:
            crew.manager_agent = None
        
        crew.save()
        messages.success(request, 'Crew agents updated successfully.')
    return redirect('agents:manage_crews')

@login_required
@user_passes_test(is_admin)
def manage_crews_card_view(request):
    crews = Crew.objects.all()
    context = {
        'crews': crews,
    }
    return render(request, 'agents/manage_crews_card_view.html', context)

@login_required
def crew_create_or_update(request, crew_id=None):
    if crew_id:
        crew = get_object_or_404(Crew, id=crew_id)
    else:
        crew = None

    # Get the 'next' parameter from the URL
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = CrewForm(request.POST, instance=crew)
        logger.debug(f"POST data: {request.POST}")
        if form.is_valid():
            crew = form.save(commit=False)
            
            # Handle input_variables
            input_variables = request.POST.getlist('input_variables[]')
            logger.debug(f"Input variables received: {input_variables}")
            crew.input_variables = input_variables
            
            crew.save()
            form.save_m2m()  # Save many-to-many relationships
            
            # Handle task ordering
            task_order = request.POST.getlist('task_order[]')
            logger.debug(f"Task order received: {task_order}")
            CrewTask.objects.filter(crew=crew).delete()
            for index, task_id in enumerate(task_order):
                CrewTask.objects.create(crew=crew, task_id=task_id, order=index)
            
            logger.info(f"Crew {'updated' if crew_id else 'created'} with id: {crew.id}, input_variables: {crew.input_variables}")
            messages.success(request, f'Crew {"updated" if crew_id else "created"} successfully.')
            
            # Redirect to the 'next' URL if provided, otherwise to manage_crews
            if next_url:
                return redirect(next_url)
            else:
                return redirect('agents:manage_crews')
        else:
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, f'Error {"updating" if crew_id else "creating"} crew. Please check the form.')
    else:
        form = CrewForm(instance=crew)
        input_variables = crew.input_variables if crew else []

    context = {
        'form': form,
        'crew': crew,
        'input_variables_json': json.dumps(input_variables),
        'next': next_url,  # Include the 'next' URL in the context
    }

    return render(request, 'agents/crew_form.html', context)
