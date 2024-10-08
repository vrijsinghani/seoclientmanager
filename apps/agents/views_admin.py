import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Agent, Task, Tool, Crew
from .forms import AgentForm, TaskForm, ToolForm, CrewForm
from django.http import JsonResponse
import importlib
import traceback
import os

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
            form.save()
            messages.success(request, 'Agent added successfully.')
            return redirect('agents:manage_agents')
    else:
        form = AgentForm()
    return render(request, 'agents/agent_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def edit_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    if request.method == 'POST':
        form = AgentForm(request.POST, instance=agent)
        if form.is_valid():
            form.save()
            messages.success(request, 'Agent updated successfully.')
            return redirect('agents:manage_agents')
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

@login_required
@user_passes_test(is_admin)
def manage_tasks(request):
    tasks = Task.objects.all()
    return render(request, 'agents/manage_tasks.html', {'tasks': tasks})

@login_required
@user_passes_test(is_admin)
def add_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task added successfully.')
            return redirect('agents:manage_tasks')
    else:
        form = TaskForm()
    return render(request, 'agents/task_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task updated successfully.')
            return redirect('agents:manage_tasks')
    else:
        form = TaskForm(instance=task)
    return render(request, 'agents/task_form.html', {'form': form, 'task': task})

@login_required
@user_passes_test(is_admin)
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Task deleted successfully.')
        return redirect('agents:manage_tasks')
    return render(request, 'agents/confirm_delete.html', {'object': task, 'type': 'task'})

@login_required
@user_passes_test(is_admin)
def manage_tools(request):
    tools = Tool.objects.all().order_by('-id')
    return render(request, 'agents/manage_tools.html', {'tools': tools})

@login_required
@user_passes_test(is_admin)
def add_tool(request):
    logger.info("Entering add_tool view")
    if request.method == 'POST':
        logger.info("POST request received")
        form = ToolForm(request.POST)
        logger.info(f"Form data: {request.POST}")
        if form.is_valid():
            logger.info("Form is valid")
            try:
                tool = form.save(commit=False)
                logger.info(f"Tool object created: {tool.__dict__}")
                tool.save()
                logger.info("Tool saved successfully")
                messages.success(request, 'Tool added successfully.')
                return redirect('agents:manage_tools')
            except Exception as e:
                logger.error(f"Error in tool creation: {str(e)}")
                logger.error(traceback.format_exc())
                messages.error(request, f"Error adding tool: {str(e)}")
        else:
            logger.warning(f"Form is invalid. Errors: {form.errors}")
    else:
        logger.info("GET request received")
        form = ToolForm()
    
    logger.info("Rendering tool_form.html")
    return render(request, 'agents/tool_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def edit_tool(request, tool_id):
    tool = get_object_or_404(Tool, id=tool_id)
    if request.method == 'POST':
        form = ToolForm(request.POST, instance=tool)
        if form.is_valid():
            try:
                tool = form.save(commit=False)
                # Fetch tool info to ensure name and description are set correctly
                tool_info = get_tool_info_internal(tool.tool_class)
                if tool_info.get('error'):
                    raise ValueError(tool_info['error'])
                tool.name = tool_info['name']
                tool.description = tool_info['description']
                tool.save()
                messages.success(request, 'Tool updated successfully.')
                return redirect('agents:manage_tools')
            except Exception as e:
                logger.error(f"Error updating tool: {str(e)}")
                messages.error(request, f"Error updating tool: {str(e)}")
    else:
        form = ToolForm(instance=tool)
    return render(request, 'agents/tool_form.html', {'form': form, 'tool': tool})

@login_required
@user_passes_test(is_admin)
def delete_tool(request, tool_id):
    tool = get_object_or_404(Tool, id=tool_id)
    if request.method == 'POST':
        tool.delete()
        messages.success(request, 'Tool deleted successfully.')
        return redirect('agents:manage_tools')
    return render(request, 'agents/confirm_delete.html', {'object': tool, 'type': 'tool'})

@login_required
@user_passes_test(is_admin)
def get_tool_info(request):
    tool_class = request.GET.get('tool_class')
    logger.info(f"Received request for tool_class: {tool_class}")
    
    if tool_class:
        try:
            # Log the current working directory and the full path of the tool
            cwd = os.getcwd()
            tool_path = os.path.join(cwd, 'apps', 'agents', 'tools', tool_class, f"{tool_class}.py")
            logger.info(f"Current working directory: {cwd}")
            logger.info(f"Full path of the tool: {tool_path}")
            
            # Check if the file exists
            if not os.path.exists(tool_path):
                logger.error(f"Tool file does not exist: {tool_path}")
                return JsonResponse({'error': 'Tool file not found'}, status=404)
            
            module_path = f"apps.agents.tools.{tool_class}.{tool_class}"
            logger.info(f"Attempting to import module: {module_path}")
            
            module = importlib.import_module(module_path)
            logger.info(f"Module imported successfully: {module}")
            
            # Get all classes defined in the module
            classes = [cls for name, cls in module.__dict__.items() if isinstance(cls, type)]
            logger.info(f"Classes found in the module: {classes}")
            
            # Try to find a class that ends with 'Tool' or matches the module name
            tool_class_obj = next((cls for cls in classes if cls.__name__.endswith('Tool') or cls.__name__.lower() == tool_class.lower()), None)

            if tool_class_obj is None:
                logger.error(f"Could not find a suitable Tool class in module {module_path}")
                return JsonResponse({'error': 'Tool class not found in module'}, status=404)
            
            logger.info(f"Tool class object: {tool_class_obj}")
            
            # Get name and description, with fallbacks
            name = getattr(tool_class_obj, 'name', tool_class)
            description = getattr(tool_class_obj, 'description', '')
            
            logger.info(f"Retrieved name: {name}, description: {description}")
            
            return JsonResponse({
                'name': name,
                'description': description,
            })
        except ImportError as e:
            logger.error(f"ImportError: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'error': 'Failed to import tool module'}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
    
    logger.warning("Invalid request: tool_class parameter is missing")
    return JsonResponse({'error': 'Invalid request'}, status=400)

    

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

# ... (rest of the code remains unchanged)