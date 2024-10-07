import json
import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Client, GoogleAnalyticsCredentials, SearchConsoleCredentials
from .google_auth import get_search_console_properties
from datetime import datetime, timedelta
from google.auth.exceptions import RefreshError
from apps.common.tools.google_analytics_tool import GoogleAnalyticsTool, GoogleAnalyticsCredentials as GACredentialsPydantic
from django.core.serializers.json import DjangoJSONEncoder
from apps.common.tools.user_activity_tool import user_activity_tool

logger = logging.getLogger(__name__)

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
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        property_id = ga_credentials.view_id.replace('properties/', '')

        # New method using GoogleAnalyticsTool
        logger.info("Fetching data using GoogleAnalyticsTool")
        ga_tool = GoogleAnalyticsTool(credentials=GACredentialsPydantic(
            view_id=ga_credentials.view_id,
            access_token=ga_credentials.access_token,
            refresh_token=ga_credentials.refresh_token,
            token_uri=ga_credentials.token_uri,
            ga_client_id=ga_credentials.ga_client_id,
            client_secret=ga_credentials.client_secret,
            use_service_account=ga_credentials.use_service_account,
            service_account_json=ga_credentials.service_account_json,
            user_email=ga_credentials.user_email,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        ))
        ga_tool_data = ga_tool.run(property_id=property_id, start_date=start_date, end_date=end_date)
        
        # Parse the JSON string returned by the tool
        try:
            analytics_data = json.loads(ga_tool_data['analytics_data'])
            
            # Convert the data back to JSON string using DjangoJSONEncoder
            context['analytics_data'] = json.dumps(analytics_data, cls=DjangoJSONEncoder)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            messages.error(request, "Error parsing analytics data. Please try again later.")
        
        context['start_date'] = ga_tool_data['start_date']
        context['end_date'] = ga_tool_data['end_date']
        
        logger.info("Successfully fetched data using GoogleAnalyticsTool")

    except RefreshError:
        logger.error("Google Analytics token has expired. Please re-authenticate.", exc_info=True)
        messages.error(request, "Google Analytics token has expired. Please re-authenticate.")
    except Exception as e:
        logger.error(f"Unexpected error in Google Analytics: {str(e)}", exc_info=True)
        messages.error(request, f"An error occurred while fetching Google Analytics data: {str(e)}")

    try:
        search_console_client = get_search_console_service(sc_credentials, request)
        search_console_data = get_search_console_data(search_console_client, sc_credentials.property_url, start_date, end_date)
        context['search_console_data'] = search_console_data
    except RefreshError:
        logger.error("Search Console token has expired. Please re-authenticate.", exc_info=True)
        messages.error(request, "Search Console token has expired. Please re-authenticate.")
    except Exception as e:
        logger.error(f"Unexpected error in Search Console: {str(e)}", exc_info=True)
        messages.error(request, f"An error occurred while fetching Search Console data: {str(e)}")

    #user_activity_tool.run(request.user, 'view', f"Viewed analytics for client: {client.name}", client=client)
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