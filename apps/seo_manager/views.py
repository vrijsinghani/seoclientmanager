import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from .models import Client, SEOData, GoogleAnalyticsCredentials, SearchConsoleCredentials, UserActivity
from .services import get_analytics_service, get_analytics_data
from .google_auth import get_google_auth_flow, get_analytics_accounts_oauth, get_analytics_accounts_service_account, get_search_console_properties
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from django.urls import reverse
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from .forms import ClientForm, BusinessObjectiveForm

def log_user_activity(user, category, action, client=None, details=None):
    UserActivity.objects.create(
        user=user,
        client=client,
        category=category,
        action=action,
        details=details
    )

@login_required
def dashboard(request):
    clients = Client.objects.all().order_by('name')
    #log_user_activity(request.user, 'view', 'Viewed dashboard')
    return render(request, 'seo_manager/dashboard.html', {'clients': clients})

@login_required
def client_list(request):
    clients = Client.objects.all().order_by('name').select_related('group')
    #log_user_activity(request.user, 'view', 'Viewed client list')
    return render(request, 'seo_manager/client_list.html', {'clients': clients})

@login_required
def add_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            log_user_activity(request.user, 'create', f"Added new client: {client.name}", client=client)
            messages.success(request, f"Client '{client.name}' has been added successfully.")
            return redirect('seo_manager:client_detail', client_id=client.id)
    else:
        form = ClientForm()
    
    return render(request, 'seo_manager/add_client.html', {'form': form})

@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    seo_data = SEOData.objects.filter(client=client).order_by('-date')[:30]
    
    credential_keys = ['accounts', 'properties', 'access_token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'service_account_json']
    for key in credential_keys:
        request.session.pop(key, None)
    
    if request.method == 'POST':
        form = BusinessObjectiveForm(request.POST)
        if form.is_valid():
            new_objective = {
                'goal': form.cleaned_data['goal'],
                'metric': form.cleaned_data['metric'],
                'target_date': form.cleaned_data['target_date'].isoformat(),
                'status': form.cleaned_data['status'],
                'date_created': datetime.now().isoformat(),
                'date_last_modified': datetime.now().isoformat(),
            }
            client.business_objectives.append(new_objective)
            client.save()
            log_user_activity(request.user, 'create', f"Added business objective for client: {client.name}", client=client, details=new_objective)
            messages.success(request, "Business objective added successfully.")
            return redirect('seo_manager:client_detail', client_id=client.id)
    else:
        form = BusinessObjectiveForm()
    
    log_user_activity(request.user, 'view', f"Viewed client details: {client.name}", client=client)
    
    # Fetch client activities
    client_activities = UserActivity.objects.filter(client=client).order_by('-timestamp')
    
    context = {
        'client': client,
        'seo_data': seo_data,
        'business_objectives': client.business_objectives,
        'form': form,
        'client_activities': client_activities,
    }
    
    return render(request, 'seo_manager/client_detail.html', context)

@login_required
def edit_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            log_user_activity(request.user, 'update', f"Updated client details: {client.name}", client=client)
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
            log_user_activity(request.user, 'update', f"Updated business objective for client: {client.name}", client=client, details=updated_objective)
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
        log_user_activity(request.user, 'delete', f"Deleted business objective for client: {client.name}", client=client, details=deleted_objective)
        messages.success(request, "Business objective deleted successfully.")
    return redirect('seo_manager:client_detail', client_id=client_id)

@login_required
def delete_client(request, client_id):
    if request.method == 'POST':
        client = get_object_or_404(Client, id=client_id)
        log_user_activity(request.user, 'delete', f"Deleted client: {client.name}", client=client)
        client.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
def client_analytics(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    ga_credentials = get_object_or_404(GoogleAnalyticsCredentials, client=client)
    sc_credentials = get_object_or_404(SearchConsoleCredentials, client=client)
    
    context = {
        'client': client,
        'analytics_data': None,
        'search_console_data': None,
        'start_date': None,
        'end_date': None,
    }

    try:
        analytics_client = get_analytics_service(ga_credentials, request)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        property_id = ga_credentials.view_id.replace('properties/', '')

        analytics_data = get_analytics_data(analytics_client, property_id, start_date, end_date)
        processed_data = process_analytics_data(analytics_data)
        context['analytics_data'] = json.dumps(processed_data)
        context['start_date'] = start_date
        context['end_date'] = end_date
    except RefreshError:
        messages.error(request, "Google Analytics token has expired. Please re-authenticate.")
    except Exception as e:
        print("Unexpected error in Google Analytics:", str(e))
        messages.error(request, "An error occurred while fetching Google Analytics data.")

    try:
        search_console_client = get_search_console_service(sc_credentials, request)
        search_console_data = get_search_console_data(search_console_client, sc_credentials.property_url, start_date, end_date)
        context['search_console_data'] = search_console_data
    except RefreshError:
        messages.error(request, "Search Console token has expired. Please re-authenticate.")
    except Exception as e:
        print("Unexpected error in Search Console:", str(e))
        messages.error(request, "An error occurred while fetching Search Console data.")

    log_user_activity(request.user, 'view', f"Viewed analytics for client: {client.name}", client=client)
    return render(request, 'seo_manager/client_analytics.html', context)
        
def extract_source_data(analytics_data):
    source_data = []
    for row in analytics_data.rows:
        source_medium = row.dimension_values[1].value
        sessions = int(row.metric_values[0].value)
        
        existing_entry = next((item for item in source_data if item['source_medium'] == source_medium), None)
        
        if existing_entry:
            existing_entry['sessions'] += sessions
        else:
            source_data.append({
                'source_medium': source_medium,
                'sessions': sessions,
            })
    
    source_data.sort(key=lambda x: x['sessions'], reverse=True)
    
    return source_data

def process_analytics_data(response):
    processed_data = []
    for row in response.rows:
        date = datetime.strptime(row.dimension_values[0].value, '%Y%m%d').strftime('%Y-%m-%d')
        sessions = int(row.metric_values[0].value)
        page_views = int(row.metric_values[1].value)
        processed_data.append({
            'date': date,
            'sessions': sessions,
            'pageviews': page_views
        })
    processed_data.sort(key=lambda x: x['date'])
    return processed_data

@login_required
def client_search_console(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    log_user_activity(request.user, 'view', f"Viewed search console data for client: {client.name}", client=client)
    return render(request, 'seo_manager/client_search_console.html', {'client': client})

@login_required
def client_ads(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    log_user_activity(request.user, 'view', f"Viewed ads data for client: {client.name}", client=client)
    return render(request, 'seo_manager/client_ads.html', {'client': client})

@login_required
def client_dataforseo(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    log_user_activity(request.user, 'view', f"Viewed DataForSEO data for client: {client.name}", client=client)
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
                log_user_activity(request.user, 'create', f"Added Google Analytics credentials (OAuth) for client: {client.name}", client=client)
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
                    log_user_activity(request.user, 'create', f"Added Google Analytics credentials (Service Account) for client: {client.name}", client=client)
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
        log_user_activity(request.user, 'delete', f"Removed Google Analytics credentials for client: {client.name}", client=client)
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
                log_user_activity(request.user, 'create', f"Added Search Console credentials for client: {client.name}", client=client)
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
            log_user_activity(request.user, 'delete', f"Removed Search Console credentials for client: {client.name}", client=client)
            messages.success(request, "Search Console credentials removed successfully.")
        else:
            messages.warning(request, "No Search Console credentials found for this client.")
    except Exception as e:
        messages.error(request, f"Error removing Search Console credentials: {str(e)}")
    
    for key in ['properties', 'access_token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']:
        request.session.pop(key, None)
    
    return redirect('seo_manager:client_detail', client_id=client.id)

def get_search_console_service(credentials, request):
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    
    creds = Credentials(
        token=credentials.access_token,
        refresh_token=credentials.refresh_token,
        token_uri=credentials.token_uri,
        client_id=credentials.sc_client_id,
        client_secret=credentials.client_secret
    )
    
    return build('searchconsole', 'v1', credentials=creds)

def get_search_console_data(service, property_url, start_date, end_date):
    try:
        response = service.searchanalytics().query(
            siteUrl=property_url,
            body={
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['query'],
                'rowLimit': 1000
            }
        ).execute()
        
        search_console_data = []
        for row in response.get('rows', []):
            search_console_data.append({
                'query': row['keys'][0],
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'] * 100,  # Convert to percentage
                'position': row['position']
            })
        
        search_console_data.sort(key=lambda x: x['impressions'], reverse=True)
        
        return search_console_data
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []

@login_required
def activity_log(request):
    activities = UserActivity.objects.all().order_by('-timestamp')
    log_user_activity(request.user, 'view', "Viewed activity log")
    return render(request, 'seo_manager/activity_log.html', {'activities': activities})