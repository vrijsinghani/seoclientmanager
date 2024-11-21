from google_auth_oauthlib.flow import Flow
from django.conf import settings
from django.urls import reverse
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import logging

logger = logging.getLogger('apps.seo_manager.google_auth')

def get_google_auth_flow(request):
    """
    Creates OAuth2 flow for Google Analytics and Search Console authentication.
    """
    flow = Flow.from_client_secrets_file(
        settings.GOOGLE_CLIENT_SECRETS_FILE,
        scopes=[
            'https://www.googleapis.com/auth/analytics.readonly',  # GA4 scope
            'https://www.googleapis.com/auth/webmasters.readonly',
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ],
        redirect_uri=request.build_absolute_uri('/google/login/callback/')
    )
    return flow

def get_analytics_accounts_oauth(credentials):
    analytics = build('analyticsadmin', 'v1alpha', credentials=credentials)
    return fetch_analytics_accounts(analytics)

def get_analytics_accounts_service_account(service_account_json):
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(service_account_json),
        scopes=['https://www.googleapis.com/auth/analytics.readonly']
    )
    analytics = build('analyticsadmin', 'v1alpha', credentials=credentials)
    return fetch_analytics_accounts(analytics)

def fetch_analytics_accounts(analytics):
    accounts = []
    account_summaries = analytics.accountSummaries().list().execute()
    
    for account_summary in account_summaries.get('accountSummaries', []):
        account_id = account_summary['account']
        account_name = account_summary['displayName']
        
        for property_summary in account_summary.get('propertySummaries', []):
            property_id = property_summary['property']
            property_name = property_summary['displayName']
            
            accounts.append({
                'account_id': account_id,
                'account_name': account_name,
                'property_id': property_id,
                'property_name': property_name,
            })
    
    return accounts

def get_search_console_service(credentials):
    return build('searchconsole', 'v1', credentials=credentials)

def get_search_console_properties(credentials_or_json):
    """
    Get list of Search Console properties using either OAuth credentials or service account JSON
    
    Args:
        credentials_or_json: Either an OAuth credentials object or service account JSON string
        
    Returns:
        list: List of Search Console properties
    """
    try:
        # Handle service account JSON string
        if isinstance(credentials_or_json, str):
            service_account_info = json.loads(credentials_or_json)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/webmasters.readonly']
            )
        else:
            # Use provided OAuth credentials
            credentials = credentials_or_json

        # Build service with appropriate credentials
        service = build('searchconsole', 'v1', credentials=credentials)
        sites = service.sites().list().execute()
        properties = []
        if 'siteEntry' in sites:
            for site in sites['siteEntry']:
                logger.info(f"site: {site}")
                properties.append({
                    'url': site['siteUrl'],
                    'permission_level': site.get('permissionLevel', '')
                })
        
        return properties

    except Exception as e:
        logger.error(f"Error getting Search Console properties: {str(e)}")
        raise