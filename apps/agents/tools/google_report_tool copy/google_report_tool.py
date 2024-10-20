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

# Import Django models
from django.core.exceptions import ObjectDoesNotExist
from apps.seo_manager.models import Client, GoogleAnalyticsCredentials

logger = logging.getLogger(__name__)

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
    name: str = "Google Analytics Report Fetcher"
    description: str = "Fetches Google Analytics report for a specified client and date range."
    args_schema: Type[BaseModel] = GoogleReportToolInput

    def __init__(self, **kwargs):
        super().__init__()

    def _get_analytics_service(self, credentials):        
        try:
            if credentials.use_service_account:
                logger.info("Using service account")
                service_account_info = json.loads(credentials.service_account_json)
                creds = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=credentials.scopes or ['https://www.googleapis.com/auth/analytics.readonly']
                )
            else:
                logger.info("Using OAuth credentials")
                creds = Credentials(
                    token=credentials.access_token,
                    refresh_token=credentials.refresh_token,
                    token_uri=credentials.token_uri,
                    client_id=credentials.ga_client_id,
                    client_secret=credentials.client_secret,
                    scopes=credentials.scopes or ['https://www.googleapis.com/auth/analytics.readonly']
                )
            
            request = Request()
            creds.refresh(request)
            
            analytics_client = BetaAnalyticsDataClient(credentials=creds)
            return analytics_client
        except Exception as e:
            logger.error(f"Error creating analytics service: {str(e)}", exc_info=True)
            raise

    def _run(self, start_date: str, end_date: str, client_id: int, **kwargs: Any) -> Any:
        try:
            # Retrieve the client's GoogleAnalyticsCredentials
            try:
                client = Client.objects.get(id=client_id)
                credentials = client.ga_credentials
            except ObjectDoesNotExist:
                raise ValueError(f"Client with id {client_id} not found or has no Google Analytics credentials")

            client = self._get_analytics_service(credentials)
            
            property_id = credentials.view_id
                        
            request = RunReportRequest(
                property=property_id,
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
            response = client.run_report(request)
            logger.info(f"response {response}")
            processed_data = self._process_analytics_data(response)
            
            result = {
                'analytics_data': json.dumps(processed_data),
                'start_date': start_date,
                'end_date': end_date,
                'client_id': client_id
            }
            return result
        except Exception as e:
            logger.error(f"Failed to fetch Google Analytics data. Error: {str(e)}", exc_info=True)
            print(f"GoogleAnalyticsTool error: {str(e)}")  # Print to stdout for immediate visibility
            return {
                'analytics_data': json.dumps([]),
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
            
            # Sort by total_users in descending order
            processed_data.sort(key=lambda x: x['total_users'], reverse=True)
        except Exception as e:
            logger.error(f"Error processing analytics data: {str(e)}", exc_info=True)
            print(f"Error processing analytics data: {str(e)}")  # Print to stdout for immediate visibility
        return processed_data

