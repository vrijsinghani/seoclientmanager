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
import google.auth.transport.requests

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

    def _run(self, start_date: str, end_date: str, client_id: int, **kwargs: Any) -> Any:
        try:
            # Retrieve the client's credentials
            try:
                client = Client.objects.get(id=client_id)
                ga_credentials = client.ga_credentials
                sc_credentials = client.sc_credentials
                
                if not ga_credentials or not sc_credentials:
                    raise ValueError("Missing Google Analytics or Search Console credentials")
                
                logger.info(f"GA Credentials - Token URI: {ga_credentials.token_uri}, Has refresh token: {bool(ga_credentials.refresh_token)}")
                logger.info(f"SC Credentials - Token URI: {sc_credentials.token_uri}, Has refresh token: {bool(sc_credentials.refresh_token)}")
                
            except ObjectDoesNotExist:
                raise ValueError(f"Client with id {client_id} not found or has missing credentials")

            # Initialize services using model methods
            try:
                analytics_client = ga_credentials.get_service()
                property_id = ga_credentials.view_id
                if not property_id:
                    raise ValueError("Missing Google Analytics property ID")
                    
                # Clean up property ID
                property_id = property_id.replace('properties/', '')
                if not property_id.isdigit():
                    raise ValueError(f"Invalid Google Analytics property ID format. Expected numeric ID, got: {property_id}")
                    
            except AuthError as e:
                logger.error(f"Failed to initialize Google Analytics service: {str(e)}")
                raise

            try:
                search_console_service = sc_credentials.get_service()
                property_url = sc_credentials.property_url
                if not property_url:
                    raise ValueError("Missing Search Console property URL")
            except AuthError as e:
                logger.error(f"Failed to initialize Search Console service: {str(e)}")
                raise
                      
            # Fetch general analytics data
            analytics_data = []
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
                analytics_data = self._process_analytics_data(general_response)
                
                if not analytics_data:
                    logger.warning("No analytics data returned from Google Analytics")
                
            except Exception as e:
                logger.error(f"Failed to fetch analytics data: {str(e)}")
                if 'invalid_grant' in str(e) or 'expired' in str(e):
                    raise AuthError(f"Google Analytics credentials have expired: {str(e)}")
                raise
            
            # Fetch Search Console data
            keyword_data = []
            landing_page_data = []
            try:
                keyword_data = self._get_search_console_data(search_console_service, property_url, start_date, end_date, 'query')
                landing_page_data = self._get_search_console_data(search_console_service, property_url, start_date, end_date, 'page')
                
                if not keyword_data and not landing_page_data:
                    logger.warning("No data returned from Search Console")
                    
            except Exception as e:
                logger.error(f"Failed to fetch Search Console data: {str(e)}")
                if 'invalid_grant' in str(e) or 'expired' in str(e):
                    raise AuthError(f"Search Console credentials have expired: {str(e)}")
                raise
            
            # Check if we got any data at all
            if not analytics_data and not keyword_data and not landing_page_data:
                return {
                    'success': False,
                    'error': "No data was collected from either Google Analytics or Search Console",
                    'analytics_data': json.dumps([]),
                    'keyword_data': json.dumps([]),
                    'landing_page_data': json.dumps([]),
                    'start_date': start_date,
                    'end_date': end_date,
                    'client_id': client_id
                }
            
            return {
                'success': True,
                'analytics_data': json.dumps(analytics_data),
                'keyword_data': json.dumps(keyword_data),
                'landing_page_data': json.dumps(landing_page_data),
                'start_date': start_date,
                'end_date': end_date,
                'client_id': client_id
            }
            
        except AuthError as e:
            logger.error(f"Authentication error: {str(e)}")
            return self._error_response(start_date, end_date, client_id, str(e))
        except Exception as e:
            logger.error(f"Failed to fetch Google Analytics or Search Console data. Error: {str(e)}", exc_info=True)
            return self._error_response(start_date, end_date, client_id, str(e))

    def _error_response(self, start_date, end_date, client_id, error):
        """Helper method to return error response"""
        return {
            'success': False,
            'error': error,
            'analytics_data': json.dumps([]),
            'keyword_data': json.dumps([]),
            'landing_page_data': json.dumps([]),
            'start_date': start_date,
            'end_date': end_date,
            'client_id': client_id
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
            # Parse the property URL if needed
            if isinstance(property_url, str) and '{' in property_url:
                try:
                    data = json.loads(property_url.replace("'", '"'))  # Replace single quotes with double quotes
                    site_url = data['url']
                except (json.JSONDecodeError, KeyError):
                    site_url = property_url
            elif isinstance(property_url, dict):
                site_url = property_url['url']
            else:
                site_url = property_url

            logger.info(f"Using Search Console property URL: {site_url}")

            response = service.searchanalytics().query(
                siteUrl=site_url,  # Use the parsed URL
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
            return search_console_data[:50]
        except HttpError as error:
            logger.error(f"An error occurred while fetching Search Console data: {error}")
            print(f"An error occurred while fetching Search Console data: {error}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching Search Console data: {str(e)}")
            return []
