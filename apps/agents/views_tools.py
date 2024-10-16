import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Tool
from .forms import ToolForm
from django.http import JsonResponse
import traceback
from .utils import get_available_tools, get_tool_classes, get_tool_description, get_tool_class_obj

logger = logging.getLogger(__name__)

def is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_admin)
def manage_tools(request):
    tools = Tool.objects.all().order_by('-id')
    return render(request, 'agents/manage_tools.html', {'tools': tools})

@login_required
@user_passes_test(is_admin)
def add_tool(request):
    if request.method == 'POST':
        form = ToolForm(request.POST)
        logger.debug(f"POST data: {request.POST}")
        if form.is_valid():
            tool = form.save(commit=False)
            tool_class = form.cleaned_data['tool_class']
            tool_subclass = form.cleaned_data['tool_subclass']
            
            logger.debug(f"Adding tool: class={tool_class}, subclass={tool_subclass}")
            
            # Get the tool class object and its description
            tool_classes = get_tool_classes(tool_class)
            logger.debug(f"Available tool classes: {[cls.__name__ for cls in tool_classes]}")
            if tool_classes:
                tool_class_obj = next((cls for cls in tool_classes if cls.__name__ == tool_subclass), None)
                if tool_class_obj:
                    logger.debug(f"Tool class object: {tool_class_obj}")
                    
                    tool.description = get_tool_description(tool_class_obj)
                    logger.debug(f"Tool description: {tool.description}")
                    
                    # Save the tool
                    tool.save()
                    
                    messages.success(request, 'Tool added successfully.')
                    return redirect('agents:manage_tools')
                else:
                    messages.error(request, f'Tool subclass {tool_subclass} not found.')
            else:
                messages.error(request, 'Tool class not found.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            logger.error(f"Form errors: {form.errors}")
    else:
        form = ToolForm()
    return render(request, 'agents/tool_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def edit_tool(request, tool_id):
    tool = get_object_or_404(Tool, id=tool_id)
    if request.method == 'POST':
        form = ToolForm(request.POST, instance=tool)
        if form.is_valid():
            tool = form.save(commit=False)
            tool.name = form.cleaned_data['tool_subclass']
            tool_class = form.cleaned_data['tool_class']
            tool_subclass = form.cleaned_data['tool_subclass']
            
            tool_class_obj = get_tool_class_obj(tool_class, tool_subclass)
            tool.description = get_tool_description(tool_class_obj)
            tool.save()
            messages.success(request, 'Tool updated successfully.')
            return redirect('agents:manage_tools')
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
            tool_objects = get_tool_classes(tool_class)
            logger.debug(f"Found tool objects: {[obj.__name__ for obj in tool_objects]}")
            
            class_info = []
            for obj in tool_objects:
                description = get_tool_description(obj)
                logger.debug(f"Tool: {obj.__name__}, Description: {description}")
                class_info.append({
                    'name': obj.__name__,
                    'description': description
                })
            
            logger.debug(f"Returning class_info: {class_info}")
            return JsonResponse({
                'classes': class_info
            })
        except ImportError as e:
            logger.error(f"ImportError: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'error': f"Failed to import tool module: {str(e)}"}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'error': f"An unexpected error occurred: {str(e)}"}, status=500)
    
    logger.warning("Invalid request: tool_class parameter is missing")
    return JsonResponse({'error': 'Invalid request: tool_class parameter is missing'}, status=400)