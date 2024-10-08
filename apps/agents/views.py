from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Crew, CrewExecution
from .forms import CrewExecutionForm
from django.contrib import messages

@login_required
def crew_list(request):
    crews = Crew.objects.all()
    return render(request, 'agents/crew_list.html', {'crews': crews})

@login_required
def crew_detail(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)
    if request.method == 'POST':
        form = CrewExecutionForm(request.POST)
        if form.is_valid():
            execution = form.save(commit=False)
            execution.crew = crew
            execution.user = request.user
            execution.save()
            messages.success(request, 'Crew execution started successfully.')
            return redirect('agents:execution_detail', execution_id=execution.id)
    else:
        form = CrewExecutionForm()
    return render(request, 'agents/crew_detail.html', {'crew': crew, 'form': form})

@login_required
def execution_list(request):
    executions = CrewExecution.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'agents/execution_list.html', {'executions': executions})

@login_required
def execution_detail(request, execution_id):
    execution = get_object_or_404(CrewExecution, id=execution_id, user=request.user)
    return render(request, 'agents/execution_detail.html', {'execution': execution})
