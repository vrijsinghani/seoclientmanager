import json
import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Client, GoogleAnalyticsCredentials, SearchConsoleCredentials
from .google_auth import get_search_console_properties
from datetime import datetime, timedelta
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from apps.agents.tools.google_analytics_tool.google_analytics_tool import GoogleAnalyticsTool
from django.core.serializers.json import DjangoJSONEncoder
from apps.common.tools.user_activity_tool import user_activity_tool

logger = logging.getLogger(__name__)

@login_required
def client_analytics(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    ga_credentials = get_object_or_404(GoogleAnalyticsCredentials, client=client)
    sc_credentials = get_object_or_404(SearchConsoleCredentials, client=client)
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    context = {
        'client': client,
        'analytics_data': None,
        'search_console_data': None,
        'start_date': start_date,
        'end_date': end_date,
    }

    # Try to get Google Analytics data
    analytics_service = ga_credentials.get_service()
    if analytics_service:
        try:
            logger.info("Fetching data using GoogleAnalyticsTool")
            ga_tool = GoogleAnalyticsTool()
            
            property_id = f"properties/{ga_credentials.get_property_id()}" if not ga_credentials.view_id.startswith('properties/') else ga_credentials.view_id
            
            ga_tool_data = ga_tool._run(
                service=analytics_service,
                start_date=start_date,
                end_date=end_date,
                property_id=property_id
            )
            
            # JSON encode the array for the template
            context['analytics_data'] = json.dumps(ga_tool_data['analytics_data'])
            context['start_date'] = ga_tool_data['start_date']
            context['end_date'] = ga_tool_data['end_date']
            
        except Exception as e:
            logger.error(f"Error fetching GA data: {str(e)}")
            messages.warning(request, "Unable to fetch Google Analytics data.")
    else:
        logger.warning(f"No valid GA service for client {client.name}")
        messages.warning(request, "Google Analytics credentials are incomplete.")

    # Try to get Search Console data
    try:
        search_console_service = sc_credentials.get_service()
        if search_console_service:
            # Get properly parsed property URL
            property_url = sc_credentials.get_property_url()
            if property_url:
                logger.info(f"Using Search Console property URL: {property_url}")
                search_console_data = get_search_console_data(
                    search_console_service, 
                    property_url,  # Use the clean URL
                    start_date, 
                    end_date
                )
                context['search_console_data'] = search_console_data
            else:
                messages.warning(request, "Invalid Search Console property URL format.")
        else:
            messages.warning(request, "Search Console credentials are incomplete.")
    except Exception as e:
        logger.error(f"Error fetching Search Console data: {str(e)}")
        messages.warning(request, "Unable to fetch Search Console data.")

    return render(request, 'seo_manager/client_analytics.html', context)

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
