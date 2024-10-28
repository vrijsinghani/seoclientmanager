import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from .models import Client, SEOData, GoogleAnalyticsCredentials, SearchConsoleCredentials, UserActivity
from .google_auth import get_google_auth_flow, get_analytics_accounts_oauth, get_analytics_accounts_service_account, get_search_console_properties
from datetime import datetime, timedelta
from .forms import ClientForm, BusinessObjectiveForm, TargetedKeywordForm, KeywordBulkUploadForm, SEOProjectForm, ClientProfileForm
from apps.common.tools.user_activity_tool import user_activity_tool
from .sitemap_extractor import extract_sitemap_and_meta_tags, extract_sitemap_and_meta_tags_from_url
from django.urls import reverse
import os
from urllib.parse import urlparse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
import csv
import io
from .models import TargetedKeyword, SEOProject
from .forms import RankingImportForm
from django.db.models import Avg

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    clients = Client.objects.all().order_by('name')
    return render(request, 'seo_manager/dashboard.html', {'clients': clients})

@login_required
def client_list(request):
    clients = Client.objects.all().order_by('name').select_related('group')
    user_activity_tool.run(request.user, 'view', 'Viewed client list')
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
    client = get_object_or_404(Client, id=client_id)
    
    # Get client activities
    client_activities = UserActivity.objects.filter(
        client=client
    ).order_by('-timestamp')[:10]  # Last 10 activities
    
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
        'profile_form': ClientProfileForm(initial={'client_profile': client.client_profile}),
    }
    
    user_activity_tool.run(
        request.user, 
        'view', 
        f"Viewed client details: {client.name}", 
        client=client
    )
    
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
def edit_business_objective(request, client_id, objective_index):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        form = BusinessObjectiveForm(request.POST)
        if form.is_valid():
            updated_objective = {
                'goal': form.cleaned_data['goal'],
                'metric': form.cleaned_data['metric'],
                'target_date': form.cleaned_data['target_date'].isoformat(),
                'status': form.cleaned_data['status'],
                'date_created': client.business_objectives[objective_index]['date_created'],
                'date_last_modified': datetime.now().isoformat(),
            }
            client.business_objectives[objective_index] = updated_objective
            client.save()
            user_activity_tool.run(request.user, 'update', f"Updated business objective for client: {client.name}", client=client, details=updated_objective)
            messages.success(request, "Business objective updated successfully.")
            return redirect('seo_manager:client_detail', client_id=client.id)
    else:
        objective = client.business_objectives[objective_index]
        initial_data = {
            'goal': objective['goal'],
            'metric': objective['metric'],
            'target_date': datetime.fromisoformat(objective['target_date']),
            'status': objective['status'],
        }
        form = BusinessObjectiveForm(initial=initial_data)
    
    context = {
        'client': client,
        'form': form,
        'objective_index': objective_index,
    }
    
    return render(request, 'seo_manager/edit_business_objective.html', context)

@login_required
def delete_business_objective(request, client_id, objective_index):
    if request.method == 'POST':
        client = get_object_or_404(Client, id=client_id)
        deleted_objective = client.business_objectives.pop(objective_index)
        client.save()
        user_activity_tool.run(request.user, 'delete', f"Deleted business objective for client: {client.name}", client=client, details=deleted_objective)
        messages.success(request, "Business objective deleted successfully.")
    return redirect('seo_manager:client_detail', client_id=client_id)

@login_required
def delete_client(request, client_id):
    if request.method == 'POST':
        client = get_object_or_404(Client, id=client_id)
        user_activity_tool.run(request.user, 'delete', f"Deleted client: {client.name}", client=client)
        client.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
def client_search_console(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    #user_activity_tool.run(request.user, 'view', f"Viewed search console data for client: {client.name}", client=client)
    return render(request, 'seo_manager/client_search_console.html', {'client': client})

@login_required
def client_ads(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    #user_activity_tool.run(request.user, 'view', f"Viewed ads data for client: {client.name}", client=client)
    return render(request, 'seo_manager/client_ads.html', {'client': client})

@login_required
def client_dataforseo(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    #user_activity_tool.run(request.user, 'view', f"Viewed DataForSEO data for client: {client.name}", client=client)
    return render(request, 'seo_manager/client_dataforseo.html', {'client': client})

def test_view(request):
    return HttpResponse("This is a test view.")

@login_required
def add_ga_credentials_oauth(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        selected_account = request.POST.get('selected_account')
        if selected_account:
            accounts = request.session.get('accounts', [])
            account_data = next((account for account in accounts if account['property_id'] == selected_account), None)
            if account_data:
                GoogleAnalyticsCredentials.objects.update_or_create(
                    client=client,
                    defaults={
                        'access_token': request.session.get('access_token', ''),
                        'refresh_token': request.session.get('refresh_token', ''),
                        'token_uri': request.session.get('token_uri', ''),
                        'ga_client_id': request.session.get('client_id', ''),
                        'client_secret': request.session.get('client_secret', ''),
                        'use_service_account': False,
                        'view_id': account_data['property_id'],
                    }
                )
                user_activity_tool.run(request.user, 'create', f"Added Google Analytics credentials (OAuth) for client: {client.name}", client=client)
                messages.success(request, "Google Analytics credentials (OAuth) added successfully.")
                return redirect('seo_manager:client_detail', client_id=client.id)
            else:
                messages.error(request, "Selected account not found. Please try again.")
        else:
            messages.error(request, "Please select an account.")
    
    if 'accounts' in request.session:
        return render(request, 'seo_manager/select_analytics_account.html', {
            'client': client,
            'accounts': request.session['accounts'],
        })
    
    flow = get_google_auth_flow(request)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=f"{client_id}_ga",
        prompt='consent'
    )
    request.session['oauth_state'] = state
    return redirect(authorization_url)

@login_required
def add_ga_credentials_service_account(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        if 'selected_account' in request.POST:
            selected_account = request.POST.get('selected_account')
            if selected_account:
                accounts = request.session.get('accounts', [])
                account_data = next((account for account in accounts if account['property_id'] == selected_account), None)
                if account_data:
                    GoogleAnalyticsCredentials.objects.update_or_create(
                        client=client,
                        defaults={
                            'service_account_json': request.session.get('service_account_json', ''),
                            'use_service_account': True,
                            'view_id': account_data['property_id'],
                        }
                    )
                    user_activity_tool.run(request.user, 'create', f"Added Google Analytics credentials (Service Account) for client: {client.name}", client=client)
                    messages.success(request, "Google Analytics credentials (Service Account) added successfully.")
                    return redirect('seo_manager:client_detail', client_id=client.id)
                else:
                    messages.error(request, "Selected account not found. Please try again.")
            else:
                messages.error(request, "Please select an account.")
        elif 'service_account_file' in request.FILES:
            service_account_file = request.FILES['service_account_file']
            try:
                service_account_info = json.load(service_account_file)
                service_account_json = json.dumps(service_account_info)
                accounts = get_analytics_accounts_service_account(service_account_json)
                request.session['accounts'] = accounts
                request.session['service_account_json'] = service_account_json
                return render(request, 'seo_manager/select_analytics_account.html', {
                    'client': client,
                    'accounts': accounts,
                })
            except json.JSONDecodeError:
                messages.error(request, "Invalid JSON file. Please upload a valid service account JSON file.")
        else:
            messages.error(request, "No file uploaded. Please select a service account JSON file.")
    
    if 'accounts' in request.session:
        return render(request, 'seo_manager/select_analytics_account.html', {
            'client': client,
            'accounts': request.session['accounts'],
        })
    
    return render(request, 'seo_manager/add_ga_credentials_service_account.html', {'client': client})

@login_required
def google_oauth_callback(request):
    state = request.GET.get('state')
    stored_state = request.session.pop('oauth_state', None)
    
    if state != stored_state:
        messages.error(request, "Invalid state parameter. Please try again.")
        return redirect('seo_manager:client_list')
    
    client_id, credential_type = state.split('_')
    client = get_object_or_404(Client, id=client_id)
    
    flow = get_google_auth_flow(request)
    flow.fetch_token(code=request.GET.get('code'))
    
    credentials = flow.credentials
    
    if credential_type == 'ga':
        accounts = get_analytics_accounts_oauth(credentials)
        request.session['accounts'] = accounts
        request.session['access_token'] = credentials.token
        request.session['refresh_token'] = credentials.refresh_token
        request.session['token_uri'] = credentials.token_uri
        request.session['client_id'] = credentials.client_id
        request.session['client_secret'] = credentials.client_secret
        return redirect('seo_manager:add_ga_credentials_oauth', client_id=client_id)
    elif credential_type == 'sc':
        properties = get_search_console_properties(credentials)
        request.session['properties'] = properties
        request.session['access_token'] = credentials.token
        request.session['refresh_token'] = credentials.refresh_token
        request.session['token_uri'] = credentials.token_uri
        request.session['client_id'] = credentials.client_id
        request.session['client_secret'] = credentials.client_secret
        return redirect('seo_manager:add_sc_credentials', client_id=client_id)
    else:
        messages.error(request, "Invalid credential type.")
        return redirect('seo_manager:client_detail', client_id=client_id)

@login_required
def remove_ga_credentials(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if client.ga_credentials:
        client.ga_credentials.delete()
        user_activity_tool.run(request.user, 'delete', f"Removed Google Analytics credentials for client: {client.name}", client=client)
        messages.success(request, "Google Analytics credentials removed successfully.")
    return redirect('seo_manager:client_detail', client_id=client.id)

@login_required
def add_sc_credentials(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        selected_property = request.POST.get('selected_property')
        if selected_property:
            try:
                SearchConsoleCredentials.objects.update_or_create(
                    client=client,
                    defaults={
                        'property_url': selected_property,
                        'access_token': request.session.get('access_token', ''),
                        'refresh_token': request.session.get('refresh_token', ''),
                        'token_uri': request.session.get('token_uri', ''),
                        'sc_client_id': request.session.get('client_id', ''),
                        'client_secret': request.session.get('client_secret', ''),
                    }
                )
                user_activity_tool.run(request.user, 'create', f"Added Search Console credentials for client: {client.name}", client=client)
                messages.success(request, "Search Console credentials added successfully.")
                
                for key in ['properties', 'access_token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']:
                    request.session.pop(key, None)
                
                return redirect('seo_manager:client_detail', client_id=client.id)
            except Exception as e:
                messages.error(request, f"Error saving Search Console credentials: {str(e)}")
        else:
            messages.error(request, "Please select a property.")
    
    if 'properties' in request.session:
        return render(request, 'seo_manager/select_search_console_property.html', {
            'client': client,
            'properties': request.session['properties'],
        })
    
    if hasattr(client, 'sc_credentials'):
        messages.warning(request, "Search Console credentials already exist for this client. Remove them first to add new ones.")
        return redirect('seo_manager:client_detail', client_id=client.id)
    
    flow = get_google_auth_flow(request)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=f"{client_id}_sc",
        prompt='consent'
    )
    request.session['oauth_state'] = state
    return redirect(authorization_url)

@login_required
def remove_sc_credentials(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    try:
        if hasattr(client, 'sc_credentials'):
            client.sc_credentials.delete()
            user_activity_tool.run(request.user, 'delete', f"Removed Search Console credentials for client: {client.name}", client=client)
            messages.success(request, "Search Console credentials removed successfully.")
        else:
            messages.warning(request, "No Search Console credentials found for this client.")
    except Exception as e:
        messages.error(request, f"Error removing Search Console credentials: {str(e)}")
    
    for key in ['properties', 'access_token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']:
        request.session.pop(key, None)
    
    return redirect('seo_manager:client_detail', client_id=client.id)

@login_required
def activity_log(request):
    activities = UserActivity.objects.all().order_by('-timestamp')
    #user_activity_tool.run(request.user, 'view', "Viewed activity log")
    return render(request, 'seo_manager/activity_log.html', {'activities': activities})

@login_required
def create_meta_tags_snapshot(request, client_id):
    if request.method == 'POST':
        client = get_object_or_404(Client, id=client_id)
        try:
            file_path = extract_sitemap_and_meta_tags(client, request.user)
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            return JsonResponse({
                'success': True,
                'message': f"Meta tags snapshot created successfully. File saved as {os.path.basename(file_path)}"
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f"An error occurred while creating the snapshot: {str(e)}"
            })
    else:
        return JsonResponse({
            'success': False,
            'message': "Invalid request method."
        })

@login_required
@require_http_methods(["POST"])
def create_meta_tags_snapshot_url(request):
    data = json.loads(request.body)
    url = data.get('url')
    if not url:
        return JsonResponse({
            'success': False,
            'message': "URL is required."
        })
    
    try:
        file_path = extract_sitemap_and_meta_tags_from_url(url, request.user)
        return JsonResponse({
            'success': True,
            'message': f"Meta tags snapshot created successfully. File saved as {os.path.basename(file_path)}"
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f"An error occurred while creating the snapshot: {str(e)}"
        })

# Add these class-based views for keyword management
class KeywordListView(LoginRequiredMixin, ListView):
    template_name = 'seo_manager/keywords/keyword_list.html'
    context_object_name = 'keywords'

    def get_queryset(self):
        return TargetedKeyword.objects.filter(client_id=self.kwargs['client_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = get_object_or_404(Client, id=self.kwargs['client_id'])
        context['import_form'] = KeywordBulkUploadForm()
        return context

class KeywordCreateView(LoginRequiredMixin, CreateView):
    model = TargetedKeyword
    form_class = TargetedKeywordForm
    template_name = 'seo_manager/keywords/keyword_form.html'

    def form_valid(self, form):
        form.instance.client_id = self.kwargs['client_id']
        response = super().form_valid(form)
        user_activity_tool.run(self.request.user, 'create', f"Added keyword: {form.instance.keyword}", client=form.instance.client)
        return response

    def get_success_url(self):
        return reverse_lazy('seo_manager:client_detail', kwargs={'client_id': self.kwargs['client_id']})

class KeywordUpdateView(LoginRequiredMixin, UpdateView):
    model = TargetedKeyword
    form_class = TargetedKeywordForm
    template_name = 'seo_manager/keywords/keyword_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        user_activity_tool.run(self.request.user, 'update', f"Updated keyword: {form.instance.keyword}", client=form.instance.client)
        return response

    def get_success_url(self):
        return reverse_lazy('seo_manager:client_detail', kwargs={'client_id': self.object.client.id})

@login_required
def keyword_import(request, client_id):
    if request.method == 'POST':
        form = KeywordBulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            client = get_object_or_404(Client, id=client_id)
            csv_file = request.FILES['csv_file']
            decoded_file = csv_file.read().decode('utf-8')
            csv_data = csv.DictReader(io.StringIO(decoded_file))
            
            for row in csv_data:
                TargetedKeyword.objects.create(
                    client=client,
                    keyword=row['keyword'],
                    priority=int(row['priority']),
                    notes=row.get('notes', '')
                )
            
            user_activity_tool.run(request.user, 'import', f"Imported keywords from CSV", client=client)
            messages.success(request, "Keywords imported successfully.")
            return redirect('seo_manager:client_detail', client_id=client_id)
    
    messages.error(request, "Invalid form submission.")
    return redirect('seo_manager:client_detail', client_id=client_id)

# Add these class-based views for project management
class ProjectListView(LoginRequiredMixin, ListView):
    template_name = 'seo_manager/projects/project_list.html'
    context_object_name = 'projects'

    def get_queryset(self):
        return SEOProject.objects.filter(client_id=self.kwargs['client_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = get_object_or_404(Client, id=self.kwargs['client_id'])
        return context

class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = SEOProject
    form_class = SEOProjectForm
    template_name = 'seo_manager/projects/project_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['client'] = get_object_or_404(Client, id=self.kwargs['client_id'])
        return kwargs

    def form_valid(self, form):
        form.instance.client_id = self.kwargs['client_id']
        # Capture initial rankings for targeted keywords
        initial_rankings = {}
        for keyword in form.cleaned_data['targeted_keywords']:
            latest_ranking = keyword.ranking_history.first()
            if latest_ranking:
                initial_rankings[keyword.keyword] = latest_ranking.average_position
        form.instance.initial_rankings = initial_rankings
        
        response = super().form_valid(form)
        user_activity_tool.run(self.request.user, 'create', f"Created SEO project: {form.instance.title}", client=form.instance.client)
        return response

    def get_success_url(self):
        return reverse_lazy('seo_manager:client_detail', kwargs={'client_id': self.kwargs['client_id']})

class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = SEOProject
    template_name = 'seo_manager/projects/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the implementation date
        implementation_date = self.object.implementation_date
        
        # Calculate periods for comparison
        pre_period_start = implementation_date - timedelta(days=30)
        post_period_end = implementation_date + timedelta(days=30)
        
        # Prepare data for the ranking history chart and performance metrics
        ranking_data = {
            'labels': [],
            'datasets': []
        }
        
        performance_metrics = []
        
        for keyword in self.object.targeted_keywords.all():
            # Get rankings for before and after implementation
            rankings = keyword.ranking_history.filter(
                date__range=(pre_period_start, post_period_end)
            ).order_by('date')
            
            # Calculate average positions for before and after
            pre_avg = rankings.filter(
                date__lt=implementation_date
            ).aggregate(Avg('average_position'))['average_position__avg']
            
            post_avg = rankings.filter(
                date__gte=implementation_date
            ).aggregate(Avg('average_position'))['average_position__avg']
            
            # Calculate improvement
            improvement = pre_avg - post_avg if pre_avg and post_avg else None
            
            # Add to performance metrics
            performance_metrics.append({
                'keyword': keyword.keyword,
                'initial_position': self.object.initial_rankings.get(keyword.keyword),
                'current_position': keyword.ranking_history.first().average_position if keyword.ranking_history.exists() else None,
                'pre_avg': round(pre_avg, 1) if pre_avg else None,
                'post_avg': round(post_avg, 1) if post_avg else None,
                'improvement': round(improvement, 1) if improvement else None
            })
            
            # Prepare chart dataset
            dataset = {
                'label': keyword.keyword,
                'data': [],
                'borderColor': f'#{hash(keyword.keyword) % 0xFFFFFF:06x}',
                'tension': 0.4,
                'fill': False
            }
            
            for ranking in rankings:
                if ranking.date.isoformat() not in ranking_data['labels']:
                    ranking_data['labels'].append(ranking.date.isoformat())
                dataset['data'].append(ranking.average_position)
            
            ranking_data['datasets'].append(dataset)
        
        # Add implementation date marker to chart
        ranking_data['implementation_date'] = implementation_date.isoformat()
        
        context.update({
            'ranking_history_data': json.dumps(ranking_data),
            'performance_metrics': performance_metrics,
            'implementation_date': implementation_date,
            'pre_period_start': pre_period_start,
            'post_period_end': post_period_end
        })
        
        return context

@login_required
def ranking_import(request, client_id):
    if request.method == 'POST':
        form = RankingImportForm(request.POST, request.FILES)
        if form.is_valid():
            form.process_import(request.user)
            messages.success(request, "Rankings imported successfully.")
            return redirect('seo_manager:client_detail', client_id=client_id)
    else:
        form = RankingImportForm()
    
    return render(request, 'seo_manager/keywords/ranking_import.html', {
        'form': form,
        'client': get_object_or_404(Client, id=client_id)
    })

@login_required
def update_client_profile(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        form = ClientProfileForm(request.POST)
        if form.is_valid():
            client.client_profile = form.cleaned_data['client_profile']
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

def edit_project(request, client_id, project_id):
    """View for editing an existing SEO project."""
    project = get_object_or_404(SEOProject, id=project_id, client_id=client_id)
    
    if request.method == 'POST':
        form = SEOProjectForm(request.POST, instance=project, client=project.client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Project updated successfully.')
            return redirect('seo_manager:client_detail', client_id=client_id)
    else:
        form = SEOProjectForm(instance=project, client=project.client)
    
    context = {
        'form': form,
        'project': project,
        'client_id': client_id,
    }
    
    return render(request, 'seo_manager/projects/edit_project.html', context)

def delete_project(request, client_id, project_id):
    """View for deleting an SEO project."""
    project = get_object_or_404(SEOProject, id=project_id, client_id=client_id)
    
    if request.method == 'POST':
        project.delete()
        messages.success(request, 'Project deleted successfully.')
        return redirect('seo_manager:client_detail', client_id=client_id)
    
    return redirect('seo_manager:client_detail', client_id=client_id)
