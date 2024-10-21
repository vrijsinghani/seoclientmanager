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
from google.analytics.data_v1beta.types import DateRange, Metric, Dimension, RunReportRequest
from google.auth.transport.requests import Request
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GACredentials(BaseModel):
  view_id: str = None
  client_id: Optional[str] = None
  access_token: str = None
  refresh_token: str = None
  token_uri: str = None
  ga_client_id: str = None
  client_secret: str = None
  use_service_account: bool = False
  service_account_json: Optional[str] = None
  user_email: str
  scopes: List[str] = []

class GoogleAnalyticsToolInput(BaseModel):
  """Input schema for GoogleAnalyticsTool."""
  start_date: str = Field(..., description="The start date for the analytics data (YYYY-MM-DD).")
  end_date: str = Field(..., description="The end date for the analytics data (YYYY-MM-DD).")
  credentials: GACredentials = Field(..., description="The credentials for the Google Analytics API.")
  @validator("start_date", "end_date")
  def validate_dates(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD.")
        
class GoogleAnalyticsTool(BaseTool):
  name: str = "Google Analytics Data Fetcher"
  description: str = "Fetches Google Analytics data for a specified property and date range."
  credentials: GACredentials = None
  args_schema: Type[BaseModel] = GoogleAnalyticsToolInput

  def __init__(self, **kwargs):
      super().__init__()
      print("GoogleAnalyticsTool initialized", file=sys.stderr)
      logger.info("GoogleAnalyticsTool initialized")
      self.credentials = kwargs.get('credentials')

  def set_credentials(self, credentials: GACredentials):
    if not isinstance(credentials, GACredentials):
        raise TypeError("credentials must be an instance of GACredentials")
    self.credentials = credentials
    logger.info(f"Credentials set: {self.credentials}")
      
  def _get_analytics_service(self):
    logger.info("Entering GoogleAnalyticsTool._get_analytics_service")
    if not self.credentials:
        raise ValueError("Credentials have not been set. Use set_credentials() method to set them.")
    
    try:
        logger.info(f"Creating analytics service for client")
        if self.credentials.use_service_account:
            logger.info("Using service account")
            service_account_info = json.loads(self.credentials.service_account_json)
            creds = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=self.credentials.scopes or ['https://www.googleapis.com/auth/analytics.readonly']
            )
        else:
            logger.info("Using OAuth credentials")
            creds = Credentials(
                token=self.credentials.access_token,
                refresh_token=self.credentials.refresh_token,
                token_uri=self.credentials.token_uri,
                client_id=self.credentials.ga_client_id,
                client_secret=self.credentials.client_secret,
                scopes=self.credentials.scopes or ['https://www.googleapis.com/auth/analytics.readonly']
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
  
  def _run(self, start_date: str, end_date: str, credentials: dict, **kwargs: Any) -> Any:
    print(f"GoogleAnalyticsTool._run called with dates: {start_date} to {end_date}", file=sys.stderr)
    logger.info(f"GoogleAnalyticsTool._run called with dates: {start_date} to {end_date}")
    try:
        logger.info(f"Entering GoogleAnalyticsTool._run with start_date: {start_date}, end_date: {end_date}")
        logger.info(f"Credentials received: {json.dumps(credentials, default=str)}")
        
        if credentials is not None:
            # Convert the dictionary to a GoogleAnalyticsCredentials object
            credentials_obj = GACredentials(**credentials)
            self.set_credentials(credentials_obj)
        
        if not self.credentials:
            raise ValueError(f"Credentials have not been set. Use set_credentials() method to set them. inputs: {start_date} - {end_date} - {kwargs}")
        
        client = self._get_analytics_service()
        
        property_id = self.credentials.view_id.replace('properties/', '')
        
        logger.info(f"Fetching analytics data for Property ID: {property_id}, Start Date: {start_date}, End Date: {end_date}")
        
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
            dimensions=[Dimension(name="date")]
        )        
        response = client.run_report(request)
        logger.info("Analytics data fetched successfully")
        
        processed_data = self._process_analytics_data(response)
        
        result = {
            'analytics_data': json.dumps(processed_data),
            'start_date': start_date,
            'end_date': end_date
        }
        logger.info(f"Returning result: {json.dumps(result, default=str)}")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch Google Analytics data. Error: {str(e)}", exc_info=True)
        print(f"GoogleAnalyticsTool error: {str(e)}")  # Print to stdout for immediate visibility
        return {
            'analytics_data': json.dumps([]),
            'start_date': start_date,
            'end_date': end_date,
            'error': str(e)
        }

  def _process_analytics_data(self, response):
    processed_data = []
    try:
        for row in response.rows:
            date = datetime.strptime(row.dimension_values[0].value, '%Y%m%d').strftime('%Y-%m-%d')
            active_users = int(row.metric_values[0].value)
            sessions = int(row.metric_values[1].value)
            processed_data.append({
                'date': date,
                'active_users': active_users,
                'sessions': sessions
            })
        processed_data.sort(key=lambda x: x['date'])
    except Exception as e:
        logger.error(f"Error processing analytics data: {str(e)}", exc_info=True)
        print(f"Error processing analytics data: {str(e)}")  # Print to stdout for immediate visibility
    return processed_data
