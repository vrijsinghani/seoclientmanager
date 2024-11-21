import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Client, GoogleAnalyticsCredentials
from ..google_auth import (
    get_google_auth_flow, 
    get_analytics_accounts_oauth, 
    get_analytics_accounts_service_account,
    get_search_console_properties
)
from apps.common.tools.user_activity_tool import user_activity_tool
import logging

logger = logging.getLogger(__name__)

@login_required
def client_ads(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    return render(request, 'seo_manager/client_ads.html', {'client': client})

@login_required
def client_dataforseo(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    return render(request, 'seo_manager/client_dataforseo.html', {'client': client})

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
    
    logger.info(f"""
    OAuth Callback received credentials for {client.name}:
    Token: {'Present' if credentials.token else 'Missing'}
    Refresh Token: {'Present' if credentials.refresh_token else 'Missing'}
    Token URI: {credentials.token_uri}
    Client ID: {credentials.client_id}
    Client Secret: {'Present' if credentials.client_secret else 'Missing'}
    """)
    
    if credential_type == 'ga':
        accounts = get_analytics_accounts_oauth(credentials)
        request.session['accounts'] = accounts
        request.session['access_token'] = credentials.token
        request.session['refresh_token'] = credentials.refresh_token
        request.session['token_uri'] = credentials.token_uri
        request.session['client_id'] = credentials.client_id
        request.session['client_secret'] = credentials.client_secret
        
        logger.info(f"""
        Storing in session for {client.name}:
        Access Token: {'Present' if credentials.token else 'Missing'}
        Refresh Token: {'Present' if credentials.refresh_token else 'Missing'}
        Token URI: {credentials.token_uri}
        Client ID: {credentials.client_id}
        Client Secret: {'Present' if credentials.client_secret else 'Missing'}
        """)
        
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
def add_ga_credentials_oauth(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    # If we don't have accounts in session, start OAuth flow
    if 'accounts' not in request.session:
        flow = get_google_auth_flow(request)
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=f"{client_id}_ga",
            prompt='consent'
        )
        request.session['oauth_state'] = state
        return redirect(authorization_url)
    
    # Handle POST request for account selection
    if request.method == 'POST':
        selected_account = request.POST.get('selected_account')
        if selected_account:
            accounts = request.session.get('accounts', [])
            account_data = next((account for account in accounts if account['property_id'] == selected_account), None)
            
            if account_data:
                logger.info(f"""
                Retrieving from session for {client.name}:
                Access Token: {'Present' if request.session.get('access_token') else 'Missing'}
                Refresh Token: {'Present' if request.session.get('refresh_token') else 'Missing'}
                Token URI: {request.session.get('token_uri')}
                Client ID: {request.session.get('client_id')}
                Client Secret: {'Present' if request.session.get('client_secret') else 'Missing'}
                """)

                credentials, created = GoogleAnalyticsCredentials.objects.update_or_create(
                    client=client,
                    defaults={
                        'access_token': request.session.get('access_token'),
                        'refresh_token': request.session.get('refresh_token'),
                        'token_uri': request.session.get('token_uri'),
                        'ga_client_id': request.session.get('client_id'),
                        'client_secret': request.session.get('client_secret'),
                        'use_service_account': False,
                        'view_id': account_data['property_id'],
                        'user_email': request.user.email,
                        'scopes': [
                            'https://www.googleapis.com/auth/analytics.readonly',
                            'https://www.googleapis.com/auth/userinfo.email',
                            'https://www.googleapis.com/auth/userinfo.profile'
                        ]
                    }
                )

                logger.info(f"""
                Saved to database for {client.name}:
                Access Token: {'Present' if credentials.access_token else 'Missing'}
                Refresh Token: {'Present' if credentials.refresh_token else 'Missing'}
                Token URI: {credentials.token_uri}
                Client ID: {credentials.ga_client_id}
                Client Secret: {'Present' if credentials.client_secret else 'Missing'}
                View ID: {credentials.view_id}
                """)

                # Clean up session
                for key in ['access_token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'accounts']:
                    request.session.pop(key, None)

                user_activity_tool.run(request.user, 'create', f"Added Google Analytics credentials (OAuth) for client: {client.name}", client=client)
                messages.success(request, "Google Analytics credentials (OAuth) added successfully.")
                return redirect('seo_manager:client_detail', client_id=client.id)
            else:
                messages.error(request, "Selected account not found. Please try again.")
        else:
            messages.error(request, "Please select an account.")
    
    # Show account selection page if we have accounts in session
    return render(request, 'seo_manager/select_analytics_account.html', {
        'client': client,
        'accounts': request.session['accounts'],
    })

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
def remove_ga_credentials(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if client.ga_credentials:
        client.ga_credentials.delete()
        user_activity_tool.run(request.user, 'delete', f"Removed Google Analytics credentials for client: {client.name}", client=client)
        messages.success(request, "Google Analytics credentials removed successfully.")
    return redirect('seo_manager:client_detail', client_id=client.id)
