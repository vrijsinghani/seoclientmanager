import logging
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, Dimension, RunReportRequest
from google.auth.transport.requests import Request
import json

logger = logging.getLogger(__name__)

def get_analytics_service(credentials):
    logger.info("Entering get_analytics_service")
    try:
        if credentials.use_service_account:
            logger.info(f"Using service account for client {credentials.client.id}")
            service_account_info = json.loads(credentials.service_account_json)
            creds = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=credentials.scopes if credentials.scopes else ['https://www.googleapis.com/auth/analytics.readonly']
            )
        else:
            logger.info(f"Using OAuth credentials for client {credentials.client.id}")
            creds = Credentials(
                token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.ga_client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes if credentials.scopes else ['https://www.googleapis.com/auth/analytics.readonly']
            )
        
        logger.info("Credentials created, refreshing...")
        request = Request()
        creds.refresh(request)
        logger.info("Credentials refreshed successfully")
        
        analytics_client = BetaAnalyticsDataClient(credentials=creds)
        logger.info("Analytics client created successfully")
        return analytics_client
    except Exception as e:
        logger.error(f"Error creating analytics service: {str(e)}", exc_info=True)
        raise
        
def get_analytics_data(client, property_id, start_date, end_date):
    logger.info("Entering get_analytics_data")
    logger.info(f"Fetching analytics data for Property ID: {property_id}, Start Date: {start_date}, End Date: {end_date}")
    try:
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[Metric(name="activeUsers"), Metric(name="screenPageViews")],
            dimensions=[Dimension(name="date"), Dimension(name="sourceMedium")]
        )
        
        response = client.run_report(request)
        logger.info("Analytics data fetched successfully")
        return response
    except Exception as e:
        logger.error(f"Error fetching analytics data: {str(e)}", exc_info=True)
        raise
    
def process_analytics_data(response):
    processed_data = []
    for row in response.rows:
        processed_data.append({
            'date': row.dimension_values[0].value,
            'active_users': row.metric_values[0].value,
            'page_views': row.metric_values[1].value
        })
    return processed_data

def get_analytics_accounts(service_account_json):
    try:
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(service_account_json),
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        analytics = build('analyticsadmin', 'v1alpha', credentials=credentials)
        
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
        
        logger.info(f"Retrieved {len(accounts)} accounts")
        return accounts
    except Exception as e:
        logger.error(f"Error in get_analytics_accounts: {str(e)}", exc_info=True)
        raise

def get_analytics_accounts_oauth(credentials):
    try:
        analytics = build('analyticsadmin', 'v1alpha', credentials=credentials)
        
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
        
        logger.info(f"Retrieved {len(accounts)} accounts via OAuth")
        return accounts
    except Exception as e:
        logger.error(f"Error in get_analytics_accounts_oauth: {str(e)}", exc_info=True)
        raise