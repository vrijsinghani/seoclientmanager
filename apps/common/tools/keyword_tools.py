import os
import requests
from langchain.tools import BaseTool
from pydantic.v1 import BaseModel, Field
from typing import Type, Optional, List, Dict, Any, Tuple


class KeywordsInput(BaseModel):
    keywords: List[str] = Field(description="list of keywords")
    filters: List[Tuple[str, str, float]] = Field(description="list of filters")

class KeywordsForSiteTool(BaseTool):
    name = "keywords_for_site"
    description = "Provides a list of keywords relevant to the target domain. Each keyword is supplied with relevant categories, search volume data for the last month, cost-per-click, competition, and search volume trend values for the past 12 months"

    def _run(self, target: str) -> str:
        login, password = KeywordTools._dataforseo_credentials()
        cred = (login, password)
        url = "https://api.dataforseo.com/v3/keywords_data/google_ads/keywords_for_site/live"
        payload = [
            {
                "target": target,
                "language_code": "en",
                "location_code": 2840,
            }
        ]
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=cred)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        results = response.json()
        return results["tasks"][0]["result"]

    def _arun(self, target: str) -> str:
        raise NotImplementedError("KeywordsForSiteTool does not support async")

class KeywordSuggestionsTool(BaseTool):
    name = "keyword_suggestions"
    description = "Provides a list of keywords relevant to the target domain. Each keyword is supplied with relevant categories, search volume data for the last month, cost-per-click, competition, and search volume trend values for the past 12 months"

    def _run(self, seed_keyword: str, filters: Optional[List] = None) -> str:
        login, password = KeywordTools._dataforseo_credentials()
        cred = (login, password)
        url = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_suggestions/live"
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
        #return results["tasks"][0]["result"]
        return results

    def _arun(self, seed_keyword: str, filters: Optional[List] = None) -> str:
        raise NotImplementedError("KeywordSuggestionsTool does not support async")

class KeywordIdeasTool(BaseTool):
    name = "keyword_ideas"
    description = "Provides search terms that are relevant to the product or service categories of the specified keywords. The algorithm selects the keywords which fall into the same categories as the seed keywords specified"
    args_schema: Type[BaseModel] = KeywordsInput

    def _run(self, keywords: List[str], filters: List[str]=None) -> str:
        
        
        login, password = KeywordTools._dataforseo_credentials()
        cred = (login, password)
        url = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live"
        payload = [
            {
                "keywords": keywords,
                "location_code": 2840,
                "language_code": "en",
                "include_serp_info": True,
                "limit": 100,
          }
        ]
        payload[0]["ordery_by"]="keyword_info.search_volume,desc"
        if filters:
            payload[0]["filters"] = filters
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=cred)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        results = response.json()
        return results

    def _arun(self, tool_input: Dict[str, Any]) -> Dict:
        raise NotImplementedError("KeywordSuggestionsTool does not support async")

class KeywordTools:
    @staticmethod
    def tools():
        return [KeywordsForSiteTool(), KeywordSuggestionsTool(), KeywordIdeasTool()]

    @staticmethod
    def _dataforseo_credentials():
        login = os.environ["DATAFORSEO_LOGIN"]
        password = os.environ["DATAFORSEO_PASSWORD"]
        return login, password
