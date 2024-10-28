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
from apps.seo_manager.models import (
    Client, 
    GoogleAnalyticsCredentials, 
    SearchConsoleCredentials,
    KeywordRankingHistory,
    TargetedKeyword
)
from django.db import transaction

logger = logging.getLogger(__name__)

class AuthError(Exception):
    """Custom exception for authentication errors"""
    pass

class GoogleRankingsToolInput(BaseModel):
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

class GoogleRankingsTool(BaseTool):
    name: str = "Google Analytics and Search Console Report Fetcher"
    description: str = "Fetches Google Analytics and Search Console reports for a specified client and date range."
    args_schema: Type[BaseModel] = GoogleRankingsToolInput

    def __init__(self, **kwargs):
        super().__init__()

    def _refresh_oauth_credentials(self, credentials_obj, stored_credentials):
        """Helper method to refresh OAuth credentials"""
        try:
            # Create a session for token validation
            session = google.auth.transport.requests.AuthorizedSession(credentials_obj)
            
            # Force token refresh
            request = google.auth.transport.requests.Request()
            credentials_obj.refresh(request)
            
            # Update stored credentials
            stored_credentials.access_token = credentials_obj.token
            stored_credentials.save()
            
            logger.info("Successfully refreshed and validated OAuth credentials")
            return credentials_obj
            
        except Exception as e:
            logger.error(f"Failed to refresh OAuth credentials: {str(e)}")
            raise AuthError(f"Failed to refresh OAuth credentials: {str(e)}")

    def _get_search_console_service(self, credentials):
        try:
            logger.info("Using OAuth credentials for Search Console")
            
            # Create credentials object
            creds = Credentials(
                token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.sc_client_id,
                client_secret=credentials.client_secret,
                scopes=['https://www.googleapis.com/auth/webmasters.readonly']
            )
            
            # Always refresh token before use
            creds = self._refresh_oauth_credentials(creds, credentials)
            
            return build('searchconsole', 'v1', credentials=creds, cache_discovery=False)

        except Exception as e:
            logger.error(f"Error in _get_search_console_service: {str(e)}", exc_info=True)
            raise AuthError(f"Failed to initialize Search Console service: {str(e)}")

    def _run(self, start_date: str, end_date: str, client_id: int, **kwargs: Any) -> Any:
        try:
            # Retrieve the client's credentials
            try:
                client = Client.objects.get(id=client_id)
                sc_credentials = client.sc_credentials
                
                if not sc_credentials:
                    raise ValueError("Missing Search Console credentials")
                
                # Log credential details for debugging
                logger.info(f"SC Credentials - Token URI: {sc_credentials.token_uri}, Has refresh token: {bool(sc_credentials.refresh_token)}")
                
            except ObjectDoesNotExist:
                raise ValueError(f"Client with id {client_id} not found or has missing credentials")

            # Initialize services with proper error handling
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
                      
            # Fetch Search Console data
            try:
                keyword_data = self._get_search_console_data(search_console_service, property_url, start_date, end_date, 'query')
                
                # Log the keyword data to database
                self._log_keyword_rankings(client, keyword_data, start_date)
                
            except Exception as e:
                logger.error(f"Failed to fetch or log Search Console data: {str(e)}")
                raise
            
            result = {
                'keyword_data': json.dumps(keyword_data),
                'start_date': start_date,
                'end_date': end_date,
                'client_id': client_id
            }
            
            return result

        except AuthError as e:
            logger.error(f"Authentication error: {str(e)}")

    @transaction.atomic
    def _log_keyword_rankings(self, client, keyword_data, date_str):
        """
        Log keyword ranking data to the KeywordRankingHistory model
        """
        try:
            # Convert date string to date object
            ranking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Get all targeted keywords for this client for efficient lookup
            targeted_keywords = {
                kw.keyword.lower(): kw 
                for kw in TargetedKeyword.objects.filter(client=client)
            }
            
            # Prepare bulk create list
            rankings_to_create = []
            
            for data in keyword_data:
                keyword_text = data['Keyword']
                
                # Create ranking history entry
                ranking = KeywordRankingHistory(
                    client=client,
                    keyword_text=keyword_text,
                    date=ranking_date,
                    impressions=data['Impressions'],
                    clicks=data['Clicks'],
                    ctr=data['CTR (%)'] / 100,  # Convert percentage to decimal
                    average_position=data['Avg Position']
                )
                
                # Link to TargetedKeyword if exists
                targeted_keyword = targeted_keywords.get(keyword_text.lower())
                if targeted_keyword:
                    ranking.keyword = targeted_keyword
                
                rankings_to_create.append(ranking)
            
            # Bulk create the rankings
            if rankings_to_create:
                # Delete existing rankings for this date and client to avoid duplicates
                KeywordRankingHistory.objects.filter(
                    client=client,
                    date=ranking_date
                ).delete()
                
                # Create new rankings
                KeywordRankingHistory.objects.bulk_create(
                    rankings_to_create,
                    batch_size=1000
                )
                
                logger.info(
                    f"Successfully logged {len(rankings_to_create)} keyword rankings "
                    f"for client {client.name} on {date_str}"
                )
        
        except Exception as e:
            logger.error(
                f"Error logging keyword rankings for client {client.name}: {str(e)}", 
                exc_info=True
            )
            raise

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
            return search_console_data[:1000]
        except HttpError as error:
            logger.error(f"An error occurred while fetching Search Console data: {error}")
            print(f"An error occurred while fetching Search Console data: {error}")
            return []
