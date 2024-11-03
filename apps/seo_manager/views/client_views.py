import json
import logging
import os
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.db.models import Min, Max, Q
from ..models import Client, KeywordRankingHistory, UserActivity
from ..forms import ClientForm, BusinessObjectiveForm, TargetedKeywordForm, KeywordBulkUploadForm, SEOProjectForm, ClientProfileForm
from apps.common.tools.user_activity_tool import user_activity_tool
from datetime import datetime

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    clients = Client.objects.all().order_by('name')
    return render(request, 'seo_manager/dashboard.html', {'clients': clients})

@login_required
def client_list(request):
    clients = Client.objects.all().order_by('name').select_related('group')
    return render(request, 'seo_manager/client_list.html', {'clients': clients})

@login_required
def add_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            user_activity_tool.run(request.user, 'create', f"Added new client: {client.name}", client=client)
            messages.success(request, f"Client '{client.name}' has been added successfully.")
            return redirect('seo_manager:client_detail', client_id=client.id)
    else:
        form = ClientForm()
    
    return render(request, 'seo_manager/add_client.html', {'form': form})

@login_required
def client_detail(request, client_id):
    # First get all the targeted keywords
    client = get_object_or_404(Client.objects.prefetch_related(
        'targeted_keywords'
    ), id=client_id)
    
    # Then for each keyword, get its complete history
    for keyword in client.targeted_keywords.all():
        # Get history both by keyword relationship AND by keyword_text match
        history = KeywordRankingHistory.objects.filter(
            Q(keyword=keyword) | 
            Q(keyword_text=keyword.keyword, client_id=client_id)
        ).order_by('-date')
        
        # Force evaluation and attach to keyword using a proper attribute name
        keyword.ranking_data = list(history)
        
    client_profile_html = client.client_profile
    
    # Get filtered client activities
    important_categories = ['create', 'update', 'delete', 'export', 'import', 'other']
    client_activities = UserActivity.objects.filter(
        client=client,
        category__in=important_categories
    ).order_by('-timestamp')[:10]  # Last 10 important activities
    
    # Get business objectives
    business_objectives = client.business_objectives
    
    # Initialize forms
    keyword_form = TargetedKeywordForm()
    import_form = KeywordBulkUploadForm()
    project_form = SEOProjectForm(client=client)
    business_objective_form = BusinessObjectiveForm()
    
    # Get meta tags files if they exist
    meta_tags_dir = os.path.join(settings.MEDIA_ROOT, 'meta-tags', str(client.id))
    meta_tags_files = []
    if os.path.exists(meta_tags_dir):
        meta_tags_files = sorted(
            [f for f in os.listdir(meta_tags_dir) if f.endswith('.json')],
            key=lambda x: os.path.getmtime(os.path.join(meta_tags_dir, x)),
            reverse=True
        )

    # Prepare keyword and project data with rankings
    keywords = client.targeted_keywords.all().prefetch_related('ranking_history')
    projects = client.seo_projects.all().prefetch_related(
        'targeted_keywords__ranking_history'
    )
    
    # Get ranking data statistics
    ranking_stats = KeywordRankingHistory.objects.filter(
        keyword__client_id=client_id
    ).aggregate(
        earliest_date=Min('date'),
        latest_date=Max('date')
    )
    
    latest_collection_date = ranking_stats['latest_date']
    
    # Calculate data coverage in months if we have data
    data_coverage_months = 0
    if ranking_stats['earliest_date'] and ranking_stats['latest_date']:
        date_diff = ranking_stats['latest_date'] - ranking_stats['earliest_date']
        data_coverage_months = round(date_diff.days / 30)  # Approximate months
    
    # Update this query to count unique keyword_text values
    tracked_keywords_count = KeywordRankingHistory.objects.filter(
        client_id=client_id
    ).values('keyword_text').distinct().count()
    
    context = {
        'client': client,
        'client_activities': client_activities,
        'business_objectives': business_objectives,
        'form': business_objective_form,
        'keyword_form': keyword_form,
        'import_form': import_form,
        'project_form': project_form,
        'meta_tags_files': meta_tags_files,
        'keywords': keywords,
        'projects': projects,
        'client_profile_html': client_profile_html,
        'profile_form': ClientProfileForm(initial={'client_profile': client.client_profile}),
        'latest_collection_date': latest_collection_date,
        'data_coverage_months': data_coverage_months,
        'tracked_keywords_count': tracked_keywords_count,
    }
    
    return render(request, 'seo_manager/client_detail.html', context)

@login_required
def edit_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            user_activity_tool.run(request.user, 'update', f"Updated client details: {client.name}", client=client)
            messages.success(request, f"Client '{client.name}' has been updated successfully.")
            return redirect('seo_manager:client_detail', client_id=client.id)
    else:
        form = ClientForm(instance=client)
    
    return render(request, 'seo_manager/edit_client.html', {'form': form, 'client': client})

@login_required
def delete_client(request, client_id):
    if request.method == 'POST':
        client = get_object_or_404(Client, id=client_id)
        user_activity_tool.run(request.user, 'delete', f"Deleted client: {client.name}", client=client)
        client.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
def update_client_profile(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        # Get the HTML content directly from the form
        client_profile = request.POST.get('client_profile', '')
        client.client_profile = client_profile
        client.save()
        
        user_activity_tool.run(
            request.user,
            'update',
            f"Updated client profile for: {client.name}",
            client=client
        )
        
        messages.success(request, "Client profile updated successfully.")
        return redirect('seo_manager:client_detail', client_id=client.id)
    
    messages.error(request, "Invalid form submission.")
    return redirect('seo_manager:client_detail', client_id=client.id)
