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

    @validator('start_date', 'end_date', allow_reuse=True)
    def validate_dates(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD.")

class GoogleAnalyticsTool(BaseTool):
    name: str = "Google Analytics Data Fetcher"
    description: str = "Fetches Google Analytics data for a specified property and date range."
    args_schema: Type[BaseModel] = GoogleAnalyticsToolInput
    
    def __init__(self, **kwargs):
        super().__init__()
        print("GoogleAnalyticsTool initialized", file=sys.stderr)
        logger.info("GoogleAnalyticsTool initialized")
        self._ga_credentials = kwargs.get('credentials')
        self._initialize_dimensions_metrics()

    def _initialize_dimensions_metrics(self):
        """Initialize the dimensions and metrics for GA4 reporting"""
        self._dimensions = [
            Dimension(name="date")
        ]
        
        self._metrics = [
            Metric(name="totalUsers"),
            Metric(name="sessions"),
            Metric(name="averageSessionDuration"),
            Metric(name="screenPageViews"),
            Metric(name="screenPageViewsPerSession"),
            Metric(name="newUsers"),
            Metric(name="bounceRate"),
            Metric(name="engagedSessions")
        ]

    def _run(self, service, start_date, end_date, property_id):
        """
        Run the Google Analytics report with metrics matching the dashboard
        """
        try:
            if not service:
                raise ValueError("Analytics service is required")

            request = RunReportRequest(
                property=f"properties/{property_id}" if not property_id.startswith('properties/') else property_id,
                dimensions=self._dimensions,
                metrics=self._metrics,
                date_ranges=[DateRange(
                    start_date=start_date,
                    end_date=end_date
                )],
                order_bys=[
                    OrderBy(
                        dimension=OrderBy.DimensionOrderBy(
                            dimension_name="date"
                        ),
                        desc=False
                    )
                ]
            )

            # Make the API call
            response = service.run_report(request)
            
            analytics_data = []
            
            for row in response.rows:
                date_str = row.dimension_values[0].value
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                
                try:
                    data_point = {
                        'date': formatted_date,
                        'active_users': int(float(row.metric_values[0].value or 0)),
                        'sessions': int(float(row.metric_values[1].value or 0)),
                        'avg_session_duration': float(row.metric_values[2].value or 0),
                        'page_views': int(float(row.metric_values[3].value or 0)),
                        'pages_per_session': float(row.metric_values[4].value or 0),
                        'new_users': int(float(row.metric_values[5].value or 0)),
                        'bounce_rate': float(row.metric_values[6].value or 0) * 100,
                        'engaged_sessions': int(float(row.metric_values[7].value or 0))
                    }
                    analytics_data.append(data_point)
                except (ValueError, IndexError) as e:
                    logger.error(f"Error processing row {date_str}: {str(e)}")
                    continue

            analytics_data.sort(key=lambda x: x['date'])

            return {
                'analytics_data': analytics_data,
                'start_date': start_date,
                'end_date': end_date
            }

        except Exception as e:
            logger.error(f"Error fetching GA4 data: {str(e)}")
            # Log the full error details
            logger.error("Full error details:", exc_info=True)
            raise

    def _format_duration(self, seconds):
        """Convert seconds to HH:MM:SS format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
