import os
import json
import logging
import sys
from typing import Any, Type, List, Optional
from pydantic.v1 import BaseModel, Field, validator
from crewai_tools.tools.base_tool import BaseTool
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, Dimension, RunReportRequest, OrderBy
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

# Import Django models
from django.core.exceptions import ObjectDoesNotExist
from apps.seo_manager.models import Client, GoogleAnalyticsCredentials, SearchConsoleCredentials

logger = logging.getLogger(__name__)

class AuthError(Exception):
    """Custom exception for authentication errors"""
    pass

class GoogleReportToolInput(BaseModel):
    """Input schema for GoogleReportTool."""
    start_date: str = Field(..., description="The start date for the analytics data (YYYY-MM-DD).")
    end_date: str = Field(..., description="The end date for the analytics data (YYYY-MM-DD).")
    client_id: int = Field(..., description="The ID of the client to fetch Google Analytics data for.")

    @validator("start_date", "end_date")
    def validate_dates(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD.")

class GoogleReportTool(BaseTool):
    name: str = "Google Analytics and Search Console Report Fetcher"
    description: str = "Fetches Google Analytics and Search Console reports for a specified client and date range."
    args_schema: Type[BaseModel] = GoogleReportToolInput

    def __init__(self, **kwargs):
        super().__init__()

    def _get_analytics_service(self, credentials):        
        try:
            if credentials.use_service_account:
                logger.info("Using service account for Google Analytics")
                service_account_info = json.loads(credentials.service_account_json)
                creds = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )
            else:
                logger.info("Using OAuth credentials for Google Analytics")
                creds = Credentials(
                    token=credentials.access_token,
                    refresh_token=credentials.refresh_token,
                    token_uri=credentials.token_uri,
                    client_id=credentials.ga_client_id,
                    client_secret=credentials.client_secret,
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )
            
            analytics_client = BetaAnalyticsDataClient(credentials=creds)
            return analytics_client
        except RefreshError as e:
            logger.error(f"Failed to refresh GA credentials: {str(e)}")
            raise AuthError("Google Analytics authorization has expired. Please reauthorize the application.")
        except Exception as e:
            logger.error(f"Error creating analytics service: {str(e)}", exc_info=True)
            raise

    def _get_search_console_service(self, credentials):
        try:
            logger.info("Using OAuth credentials for Search Console")
            creds = Credentials(
                token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.sc_client_id,
                client_secret=credentials.client_secret,
                scopes=['https://www.googleapis.com/auth/webmasters.readonly']
            )
            
            return build('searchconsole', 'v1', credentials=creds, cache_discovery=False)
        except RefreshError as e:
            logger.error(f"Failed to refresh SC credentials: {str(e)}")
            raise AuthError("Search Console authorization has expired. Please reauthorize the application.")
        except Exception as e:
            logger.error(f"Error creating Search Console service: {str(e)}", exc_info=True)
            raise

    def _run(self, start_date: str, end_date: str, client_id: int, **kwargs: Any) -> Any:
        try:
            # Retrieve the client's credentials
            try:
                client = Client.objects.get(id=client_id)
                ga_credentials = client.ga_credentials
                sc_credentials = client.sc_credentials
                
                if not ga_credentials or not sc_credentials:
                    raise ValueError("Missing Google Analytics or Search Console credentials")
                
            except ObjectDoesNotExist:
                raise ValueError(f"Client with id {client_id} not found or has missing credentials")

            # Initialize services with proper error handling
            try:
                analytics_client = self._get_analytics_service(ga_credentials)
                property_id = ga_credentials.view_id
                if not property_id:
                    raise ValueError("Missing Google Analytics property ID")
                    
                # Clean up property ID - ensure it's just the numeric ID
                property_id = property_id.replace('properties/', '')
                if not property_id.isdigit():
                    raise ValueError(f"Invalid Google Analytics property ID format. Expected numeric ID, got: {property_id}")
                    
            except AuthError as e:
                logger.error(f"Failed to initialize Google Analytics service: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Google Analytics service: {str(e)}")
                raise

            try:
                search_console_service = self._get_search_console_service(sc_credentials)
                property_url = sc_credentials.property_url
                if not property_url:
                    raise ValueError("Missing Search Console property URL")
            except AuthError as e:
                logger.error(f"Failed to initialize Search Console service: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Search Console service: {str(e)}")
                raise
                      
            # Fetch general analytics data
            try:
                general_request = RunReportRequest(
                    property=f"properties/{property_id}",
                    date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                    dimensions=[
                        Dimension(name="sessionSourceMedium"),
                    ],
                    metrics=[
                        Metric(name="totalUsers"),
                        Metric(name="sessions"),
                        Metric(name="bounceRate"),
                        Metric(name="averageSessionDuration"),
                    ],
                    order_bys=[
                        OrderBy(metric=OrderBy.MetricOrderBy(metric_name="totalUsers"), desc=True)
                    ],
                    limit=10
                )        
                general_response = analytics_client.run_report(general_request)
            except RefreshError as e:
                logger.error(f"Failed to refresh credentials while fetching analytics data: {str(e)}")
                raise AuthError("Authorization has expired while fetching analytics data. Please reauthorize the application.")
            
            # Fetch Search Console data
            try:
                keyword_data = self._get_search_console_data(search_console_service, property_url, start_date, end_date, 'query')
                landing_page_data = self._get_search_console_data(search_console_service, property_url, start_date, end_date, 'page')
            except RefreshError as e:
                logger.error(f"Failed to refresh credentials while fetching Search Console data: {str(e)}")
                raise AuthError("Authorization has expired while fetching Search Console data. Please reauthorize the application.")
            
            processed_general_data = self._process_analytics_data(general_response)
            
            result = {
                'analytics_data': json.dumps(processed_general_data),
                'keyword_data': json.dumps(keyword_data),
                'landing_page_data': json.dumps(landing_page_data),
                'start_date': start_date,
                'end_date': end_date,
                'client_id': client_id
            }
            
            # Create CSV files
            keyword_df = pd.DataFrame(keyword_data)
            if not keyword_df.empty:
                keyword_df.to_csv('keyword_data.csv', index=False)
            
            landing_page_df = pd.DataFrame(landing_page_data)
            if not landing_page_df.empty:
                landing_page_df.to_csv('landing_page_data.csv', index=False)
            
            return result
        except AuthError as e:
            logger.error(f"Authentication error: {str(e)}")
            return {
                'analytics_data': json.dumps([]),
                'keyword_data': json.dumps([]),
                'landing_page_data': json.dumps([]),
                'start_date': start_date,
                'end_date': end_date,
                'client_id': client_id,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Failed to fetch Google Analytics or Search Console data. Error: {str(e)}", exc_info=True)
            print(f"GoogleReportTool error: {str(e)}")  # Print to stdout for immediate visibility
            return {
                'analytics_data': json.dumps([]),
                'keyword_data': json.dumps([]),
                'landing_page_data': json.dumps([]),
                'start_date': start_date,
                'end_date': end_date,
                'client_id': client_id,
                'error': str(e)
            }
            
    def _process_analytics_data(self, response):
        processed_data = []
        try:
            for row in response.rows:
                source_medium = row.dimension_values[0].value
                total_users = int(row.metric_values[0].value)
                sessions = int(row.metric_values[1].value)
                bounce_rate = float(row.metric_values[2].value)
                avg_session_duration = float(row.metric_values[3].value)
                
                processed_data.append({
                    'source_medium': source_medium,
                    'total_users': total_users,
                    'sessions': sessions,
                    'bounce_rate': bounce_rate,
                    'avg_session_duration': avg_session_duration
                })
            
            processed_data.sort(key=lambda x: x['total_users'], reverse=True)
        except Exception as e:
            logger.error(f"Error processing analytics data: {str(e)}", exc_info=True)
            print(f"Error processing analytics data: {str(e)}")
        return processed_data

    def _get_search_console_data(self, service, property_url, start_date, end_date, dimension):
        try:
            response = service.searchanalytics().query(
                siteUrl=property_url,
                body={
                    'startDate': start_date,
                    'endDate': end_date,
                    'dimensions': [dimension],
                    'rowLimit': 1000
                }
            ).execute()
            
            search_console_data = []
            for row in response.get('rows', []):
                search_console_data.append({
                    'Keyword' if dimension == 'query' else 'Landing Page': row['keys'][0],
                    'Clicks': row['clicks'],
                    'Impressions': row['impressions'],
                    'CTR (%)': round(row['ctr'] * 100, 2),
                    'Avg Position': round(row['position'], 1)
                })
            
            search_console_data.sort(key=lambda x: x['Impressions'], reverse=True)
            return search_console_data[:100]
        except HttpError as error:
            logger.error(f"An error occurred while fetching Search Console data: {error}")
            print(f"An error occurred while fetching Search Console data: {error}")
            return []
