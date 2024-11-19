import logging
from typing import Any, Type, List, Optional
from pydantic import BaseModel, Field, field_validator
from crewai_tools.tools.base_tool import BaseTool
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, 
    Metric, 
    Dimension, 
    RunReportRequest,
    OrderBy
)
from datetime import datetime, timedelta
import json
from googleapiclient.errors import HttpError

# Import Django models
from django.core.exceptions import ObjectDoesNotExist
from apps.seo_manager.models import Client

logger = logging.getLogger(__name__)

class GoogleOverviewToolInput(BaseModel):
    """Input schema for GoogleOverviewTool."""
    client_id: int = Field(description="The ID of the client to fetch Google Analytics data for.")
    days_ago: int = Field(
        default=90,
        description="Number of days to look back (default: 90)",
        ge=1,
        le=365
    )

class GoogleOverviewTool(BaseTool):
    name: str = "Google Analytics and Search Console Overview Tool"
    description: str = "Fetches comprehensive overview reports from Google Analytics and Search Console"
    args_schema: Type[BaseModel] = GoogleOverviewToolInput

    def _run(self, client_id: int, days_ago: int = 90) -> str:
        try:
            # Calculate dates
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

            # Get client and credentials
            client = Client.objects.get(id=client_id)
            ga_credentials = client.ga_credentials
            sc_credentials = client.sc_credentials
            
            if not ga_credentials or not sc_credentials:
                raise ValueError("Missing Google Analytics or Search Console credentials")

            # Initialize services
            analytics_service = ga_credentials.get_service()
            search_console_service = sc_credentials.get_service()
            property_id = ga_credentials.get_property_id()
            property_url = sc_credentials.get_property_url()

            if not all([analytics_service, search_console_service, property_id, property_url]):
                raise ValueError("Failed to initialize required services")

            # 1. User Overview Report
            user_overview = self._fetch_analytics_report(
                analytics_service,
                property_id,
                start_date,
                end_date,
                ["date", "country"],
                ["activeUsers", "newUsers", "totalUsers"]
            )

            # 2. Session Analysis Report
            session_data = self._fetch_analytics_report(
                analytics_service,
                property_id,
                start_date,
                end_date,
                ["sessionSource", "sessionMedium"],
                ["totalUsers", "sessions", "bounceRate", "averageSessionDuration"]
            )

            # 3. Page Performance Report
            page_performance = self._fetch_analytics_report(
                analytics_service,
                property_id,
                start_date,
                end_date,
                ["date", "pagePath"],
                ["screenPageViews", "screenPageViewsPerSession", "engagementRate"]
            )

            # 4. Event Engagement Report
            event_engagement = self._fetch_analytics_report(
                analytics_service,
                property_id,
                start_date,
                end_date,
                ["date", "country"],
                ["eventCount", "eventCountPerUser"]
            )

            # Format analytics data for template compatibility
            analytics_data = []
            
            # Format session data like google_report_tool
            for row in session_data:
                analytics_data.append({
                    'source_medium': f"{row['sessionSource']} / {row['sessionMedium']}",
                    'total_users': int(row['totalUsers']),
                    'sessions': int(row['sessions']),
                    'bounce_rate': float(row['bounceRate']),
                    'avg_session_duration': float(row['averageSessionDuration'])
                })

            # Sort by total users
            analytics_data.sort(key=lambda x: x['total_users'], reverse=True)

            # 5. Search Console Overview Report
            keyword_data = self._fetch_search_console_report(
                search_console_service,
                property_url,
                start_date,
                end_date,
                ["query", "country"],
                row_limit=50
            )

            # 6. Search Performance by Page Report
            landing_page_data = self._fetch_search_console_report(
                search_console_service,
                property_url,
                start_date,
                end_date,
                ["page"]
            )

            # 7. Search Performance by Device Report
            device_performance = self._fetch_search_console_report(
                search_console_service,
                property_url,
                start_date,
                end_date,
                ["device"]
            )

            # Return all data in a format compatible with the template
            return json.dumps({
                'success': True,
                'analytics_data': analytics_data,
                'user_overview': user_overview,
                'page_performance': page_performance,
                'event_engagement': event_engagement,
                'keyword_data': keyword_data,
                'landing_page_data': landing_page_data,
                'device_performance': device_performance,
                'start_date': start_date,
                'end_date': end_date,
                'client_id': client_id
            })

        except Exception as e:
            error_message = f"Error fetching overview data: {str(e)}"
            logger.error(error_message)
            logger.error("Full error details:", exc_info=True)
            return json.dumps({
                'success': False,
                'error': str(e),
                'analytics_data': [],
                'keyword_data': [],
                'landing_page_data': []
            })

    def _fetch_analytics_report(self, service, property_id: str, start_date: str, end_date: str, 
                              dimensions: List[str], metrics: List[str]) -> List[dict]:
        try:
            dimension_objects = [Dimension(name=dim) for dim in dimensions]
            metric_objects = [Metric(name=metric) for metric in metrics]

            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=dimension_objects,
                metrics=metric_objects,
                limit=1000
            )

            response = service.run_report(request)
            
            results = []
            for row in response.rows:
                result = {}
                for i, dimension in enumerate(dimensions):
                    result[dimension] = row.dimension_values[i].value
                for i, metric in enumerate(metrics):
                    # Keep numeric values as numbers, don't format as strings
                    value = float(row.metric_values[i].value)
                    if metrics[i] in ['totalUsers', 'sessions']:
                        value = int(value)
                    result[metrics[i]] = value
                results.append(result)
                
            return results

        except Exception as e:
            logger.error(f"Error fetching analytics report: {str(e)}")
            return []

    def _fetch_search_console_report(self, service, property_url: str, start_date: str, 
                                   end_date: str, dimensions: List[str], row_limit: int = 100) -> List[dict]:
        try:
            response = service.searchanalytics().query(
                siteUrl=property_url,
                body={
                    'startDate': start_date,
                    'endDate': end_date,
                    'dimensions': dimensions,
                    'rowLimit': row_limit
                }
            ).execute()
            
            results = []
            for row in response.get('rows', []):
                result = {}
                for i, dimension in enumerate(dimensions):
                    result[dimension] = row['keys'][i]
                result.update({
                    'Clicks': int(row['clicks']),
                    'Impressions': int(row['impressions']),
                    'CTR': f"{round(row['ctr'] * 100, 2)}%",
                    'Position': round(row['position'], 1)
                })
                results.append(result)
            
            return results

        except Exception as e:
            logger.error(f"Error fetching Search Console report: {str(e)}")
            return [] 