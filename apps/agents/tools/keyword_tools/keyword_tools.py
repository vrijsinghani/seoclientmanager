import os
import requests
from typing import Any, Type, List, Dict, Tuple
from pydantic.v1 import BaseModel, Field
from crewai_tools.tools.base_tool import BaseTool
import logging
import json
import csv
import io
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

BASE_URL = os.getenv('DATAFORSEO_BASE_URL', 'https://api.dataforseo.com')

class KeywordsForSiteInput(BaseModel):
    target: str = Field(description="Target domain for keyword analysis")

class KeywordSuggestionsInput(BaseModel):
    seed_keyword: str = Field(description="Seed keyword for suggestions")
    filters: List[Tuple[str, str, float]] = Field(description="List of filters", default=[])

class KeywordIdeasInput(BaseModel):
    keywords: List[str] = Field(description="List of keywords")
    filters: List[Tuple[str, str, float]] = Field(description="List of filters", default=[])

class KeywordsForSiteTool(BaseTool):
    name: str = "Keywords for Site"
    description: str = "Provides a list of keywords relevant to the target domain. Each keyword is supplied with relevant categories, search volume data for the last month, cost-per-click, competition, and search volume trend values for the past 12 months"
    args_schema: Type[BaseModel] = KeywordsForSiteInput

    def _run(self, target: str, **kwargs: Any) -> Any:
        login, password = KeywordTools._dataforseo_credentials()
        cred = (login, password)
        url = f"{BASE_URL}/v3/keywords_data/google_ads/keywords_for_site/live"
        payload = [
            {
                "target": target,
                "language_code": "en",
                "location_code": 2840,
            }
        ]
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(url, json=payload, headers=headers, auth=cred)
            response.raise_for_status()  # Raise an exception for non-2xx status codes

        except Exception as e:
            logger.error(f"Error making request to DataForSEO: {e}")
            raise e

        json_response = response.json()
        
        try:
            results = self.transform_keyword_data(json_response)
        except Exception as e:
            logger.error(f"Error transforming keyword data: {e}")
            raise e

        return results

    async def _arun(self, target: str, **kwargs: Any) -> Any:
        raise NotImplementedError("KeywordsForSiteTool does not support async")

    def transform_keyword_data(self, data: Dict) -> str:
        """Transforms the keyword data into CSV format."""
        try:
            # Extract all results from all tasks
            all_results = [item for task in data.get('tasks', []) for item in task.get('result', [])]

            # Convert to DataFrame
            df = pd.DataFrame(all_results)

            # Process monthly_searches
            df['monthly_searches'] = df['monthly_searches'].fillna(pd.Series([[] for _ in range(len(df))]))
            df['min_search'] = df['monthly_searches'].apply(lambda x: min((m.get('search_volume', 0) or 0) for m in x) if x else 0)
            df['max_search'] = df['monthly_searches'].apply(lambda x: max((m.get('search_volume', 0) or 0) for m in x) if x else 0)
            df['avg_search_volume'] = df['monthly_searches'].apply(lambda x: sum((m.get('search_volume', 0) or 0) for m in x) / len(x) if x else 0)

            # Select and rename columns
            result_df = df[['keyword', 'avg_search_volume', 'min_search', 'max_search', 'competition', 'low_top_of_page_bid', 'high_top_of_page_bid', 'cpc']]
            result_df = result_df.rename(columns={
                'low_top_of_page_bid': 'low_top_bid',
                'high_top_of_page_bid': 'high_top_bid'
            })

            # Fill NaN values
            result_df = result_df.fillna({
                'keyword': 'N/A',
                'competition': 'NONE',
                'avg_search_volume': 0,
                'min_search': 0,
                'max_search': 0,
                'low_top_bid': 0,
                'high_top_bid': 0,
                'cpc': 0
            })

            # Sort by avg_search_volume in descending order
            result_df = result_df.sort_values('cpc', ascending=False)

            # Convert to CSV
            csv_output = result_df.to_csv(index=False)
            return csv_output

        except Exception as e:
            logger.error(f"Error transforming keyword data: {e}")
            raise e
        
class KeywordSuggestionsTool(BaseTool):
    name: str = "Keyword Suggestions"
    description: str = "Provides a list of keywords relevant to the target domain. Each keyword is supplied with relevant categories, search volume data for the last month, cost-per-click, competition, and search volume trend values for the past 12 months"
    args_schema: Type[BaseModel] = KeywordSuggestionsInput

    def _run(self, seed_keyword: str, filters: List = None, **kwargs: Any) -> Any:
        login, password = KeywordTools._dataforseo_credentials()
        cred = (login, password)
        url = f"{BASE_URL}/v3/dataforseo_labs/google/keyword_suggestions/live"
        payload = [
            {
                "keyword": seed_keyword,
                "location_code": 2840,
                "language_code": "en",
                "include_serp_info": True,
                "include_seed_keyword": True,
                "limit": 50,
            }
        ]
        if filters:
            payload[0]["filters"] = filters
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=cred)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        results = response.json()
        return results

    async def _arun(self, seed_keyword: str, filters: List = None, **kwargs: Any) -> Any:
        raise NotImplementedError("KeywordSuggestionsTool does not support async")

class KeywordIdeasTool(BaseTool):
    name: str = "Keyword Ideas"
    description: str = "Provides search terms that are relevant to the product or service categories of the specified keywords. The algorithm selects the keywords which fall into the same categories as the seed keywords specified"
    args_schema: Type[BaseModel] = KeywordIdeasInput

    def _run(self, keywords: List[str], filters: List[Tuple[str, str, float]] = None, **kwargs: Any) -> Any:
        login, password = KeywordTools._dataforseo_credentials()
        cred = (login, password)
        url = f"{BASE_URL}/v3/dataforseo_labs/google/keyword_ideas/live"
        payload = [
            {
                "keywords": keywords,
                "location_code": 2840,
                "language_code": "en",
                "include_serp_info": True,
                "limit": 100,
            }
        ]
        payload[0]["order_by"] = "keyword_info.search_volume,desc"
        if filters:
            payload[0]["filters"] = filters
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=cred)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        results = response.json()
        return results

    async def _arun(self, keywords: List[str], filters: List[Tuple[str, str, float]] = None, **kwargs: Any) -> Any:
        raise NotImplementedError("KeywordIdeasTool does not support async")

class KeywordTools:
    @staticmethod
    def tools():
        return [KeywordsForSiteTool(), KeywordSuggestionsTool(), KeywordIdeasTool()]

    @staticmethod
    def _dataforseo_credentials():
        login = os.environ["DATAFORSEO_EMAIL"]
        password = os.environ["DATAFORSEO_PASSWORD"]
        return login, password
