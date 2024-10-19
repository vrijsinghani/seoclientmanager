import os
import requests
from typing import Any, Type, List, Dict, Tuple
from pydantic.v1 import BaseModel, Field
from crewai_tools.tools.base_tool import BaseTool
import logging
import json

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

    def transform_keyword_data(self, data: Dict) -> List[str]:
        """Transforms the keyword data into a more LLM-friendly format."""
        transformed_data = []

        try:
            tasks = data.get('tasks', [])
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            raise e

        for task in tasks:
            try:
                results = task.get('result', [])
            except Exception as e:
                logger.error(f"Error getting result: {e}")
                raise e

            for item in results:
                try:
                    keyword = item.get('keyword', 'N/A')
                    search_volume = item.get('search_volume', 0)
                    competition = item.get('competition', 'N/A')
                    low_top_of_page_bid = item.get('low_top_of_page_bid', 0)
                    high_top_of_page_bid = item.get('high_top_of_page_bid', 0)
                    cpc = item.get('cpc', 0)
                    monthly_searches = item.get('monthly_searches', [])

                    if monthly_searches:
                        min_search = min((m.get('search_volume', 0) or 0) for m in monthly_searches)
                        max_search = max((m.get('search_volume', 0) or 0) for m in monthly_searches)
                        avg_search_volume = sum((m.get('search_volume', 0) or 0) for m in monthly_searches) / len(monthly_searches) if monthly_searches else 0
                    else:
                        min_search = max_search = avg_search_volume = 0

                    try:
                        summary = {
                            "keyword": keyword,
                            "avg_search_volume": avg_search_volume,
                            "min_search": min_search,
                            "max_search": max_search,
                            "competition": competition,
                            "low_top_bid": low_top_of_page_bid,
                            "high_top_bid": high_top_of_page_bid,
                            "cpc": cpc,
                        }
                    except Exception as e:
                        logger.error(f"Error processing item summary: {item}, Error: {e}")  

                    transformed_data.append(summary)
                except Exception as e:
                    logger.error(f"Error processing item: {item}, Error: {e}")

        # Sort transformed_data by avg_search_volume in descending order
        transformed_data.sort(key=lambda x: x['avg_search_volume'], reverse=True)

        # Format the sorted data for output
        formatted_data=[]

        for item in transformed_data:
            try:
                # Check for None values and handle them
                avg_search_volume = item['avg_search_volume'] if item['avg_search_volume'] is not None else 0
                min_search = item['min_search'] if item['min_search'] is not None else 0
                max_search = item['max_search'] if item['max_search'] is not None else 0
                low_top_bid = item['low_top_bid'] if item['low_top_bid'] is not None else 0
                high_top_bid = item['high_top_bid'] if item['high_top_bid'] is not None else 0
                cpc = item['cpc'] if item['cpc'] is not None else 0

                formatted_data.append(
                    (f"Keyword: {item['keyword']}, Avg. Monthly Searches: {avg_search_volume:.0f}, "
                    f"Min: {min_search}, Max: {max_search}, Competition: {item['competition']}, "
                    f"Low Top Bid: ${low_top_bid:.2f}, High Top Bid: ${high_top_bid:.2f}, "
                    f"CPC: ${cpc:.2f}")
                )
            except Exception as e:
                logger.error(f"Error formatting item: {item}, Error: {e}")


        return formatted_data

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
