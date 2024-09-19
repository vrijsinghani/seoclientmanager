import json  # Add this import at the top of the file
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Client, SEOData, GoogleAnalyticsCredentials, SearchConsoleCredentials
from .services import get_analytics_service, get_analytics_data
from .google_auth import get_google_auth_flow, get_analytics_accounts_oauth, get_analytics_accounts_service_account, get_search_console_properties
from datetime import datetime, timedelta
from django.http import HttpResponse
from google_auth_oauthlib.flow import Flow
from django.urls import reverse

@login_required
def dashboard(request):
    total_clients = Client.objects.count()
    return render(request, 'seo_manager/dashboard.html', {'total_clients': total_clients})

def client_list(request):
    clients = Client.objects.all()
    return render(request, 'seo_manager/client_list.html', {'clients': clients})

@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    seo_data = SEOData.objects.filter(client=client).order_by('-date')[:30]
    
    # Clear all credential-related session data
    credential_keys = ['accounts', 'properties', 'access_token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'service_account_json']
    for key in credential_keys:
        request.session.pop(key, None)
    
    context = {
        'client': client,
        'seo_data': seo_data,
    }
    
    return render(request, 'seo_manager/client_detail.html', context)

@login_required
def client_analytics(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    ga_credentials = get_object_or_404(GoogleAnalyticsCredentials, client=client)
    
    service = get_analytics_service(ga_credentials)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    analytics_data = get_analytics_data(service, ga_credentials.view_id, start_date, end_date)
    
    # Process the analytics_data to extract relevant information
    processed_data = process_analytics_data(analytics_data)
    
    return render(request, 'seo_manager/client_analytics.html', {
        'client': client,
        'analytics_data': processed_data
    })

def process_analytics_data(analytics_data):
    # Extract and process the relevant data from the API response
    # This is a simplified example, you may want to expand this based on your needs
    processed_data = []
    for report in analytics_data.get('reports', []):
        for row in report.get('data', {}).get('rows', []):
            date = row['dimensions'][0]
            sessions = row['metrics'][0]['values'][0]
            pageviews = row['metrics'][0]['values'][1]
            processed_data.append({
                'date': date,
                'sessions': sessions,
                'pageviews': pageviews
            })
    return processed_data

@login_required
def client_search_console(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    # Implement Google Search Console data fetching here
    return render(request, 'seo_manager/client_search_console.html', {'client': client})

@login_required
def client_ads(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    # Implement Google Ads data fetching here
    return render(request, 'seo_manager/client_ads.html', {'client': client})

@login_required
def client_dataforseo(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    # Implement DataForSEO data fetching here
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
                messages.success(request, "Search Console credentials added successfully.")
                
                # Clear session data after successful addition
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
    
    # Check if credentials already exist
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
            messages.success(request, "Search Console credentials removed successfully.")
        else:
            messages.warning(request, "No Search Console credentials found for this client.")
    except Exception as e:
        messages.error(request, f"Error removing Search Console credentials: {str(e)}")
    
    # Clear session data related to SC credentials
    for key in ['properties', 'access_token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']:
        request.session.pop(key, None)
    
    return redirect('seo_manager:client_detail', client_id=client.id)