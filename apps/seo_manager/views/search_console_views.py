from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Client, SearchConsoleCredentials
from ..google_auth import get_google_auth_flow, get_search_console_properties
from apps.common.tools.user_activity_tool import user_activity_tool
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def client_search_console(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    return render(request, 'seo_manager/client_search_console.html', {'client': client})

@login_required
def add_sc_credentials(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        selected_property = request.POST.get('selected_property')
        if selected_property:
            try:
                # Extract just the URL
                try:
                    # Try to parse as JSON
                    property_data = json.loads(selected_property)
                    property_url = property_data['url']
                except (json.JSONDecodeError, KeyError):
                    # If not JSON or missing url key, use as-is
                    property_url = selected_property

                logger.info(f"""
                    Storing Search Console credentials for {client.name}:
                    property_url: {property_url}  # Now just the URL string
                    access_token: {bool(request.session.get('access_token'))}
                    refresh_token: {bool(request.session.get('refresh_token'))}
                    token_uri: {bool(request.session.get('token_uri'))}
                    client_id: {bool(request.session.get('client_id'))}
                    client_secret: {bool(request.session.get('client_secret'))}
                """)

                credentials = SearchConsoleCredentials.objects.update_or_create(
                    client=client,
                    defaults={
                        'property_url': property_url,  # Now just the URL string
                        'access_token': request.session.get('access_token'),
                        'refresh_token': request.session.get('refresh_token'),
                        'token_uri': request.session.get('token_uri'),
                        'sc_client_id': request.session.get('client_id'),
                        'client_secret': request.session.get('client_secret'),
                    }
                )[0]
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
