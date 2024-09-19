from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.conf import settings
import os

def get_analytics_service(ga_credentials):
    credentials = Credentials(
        token=ga_credentials.access_token,
        refresh_token=ga_credentials.refresh_token,
        token_uri=ga_credentials.token_uri,
        client_id=ga_credentials.client_id,
        client_secret=ga_credentials.client_secret,
        scopes=ga_credentials.scopes
    )
    return build('analyticsreporting', 'v4', credentials=credentials)

def get_analytics_data(service, view_id, start_date, end_date):
    return service.reports().batchGet(
        body={
            'reportRequests': [
                {
                    'viewId': view_id,
                    'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                    'metrics': [{'expression': 'ga:sessions'}, {'expression': 'ga:pageviews'}],
                    'dimensions': [{'name': 'ga:date'}]
                }
            ]
        }
    ).execute()