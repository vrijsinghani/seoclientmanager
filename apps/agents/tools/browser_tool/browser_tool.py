import json
import os
from typing import Any, Type, Set
import logging

import requests
from pydantic import BaseModel, Field
from trafilatura import extract
from crewai_tools import BaseTool as CrewAIBaseTool
from urllib.parse import urljoin, urlparse
import dotenv

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

class BrowserToolSchema(BaseModel):
    """Input for BrowserTool."""
    website: str = Field(..., description="Full URL of the website to scrape (e.g., https://google.com)")

class BrowserTool(CrewAIBaseTool):
    name: str = "Scrape website content"
    description: str = "A tool that can be used to scrape website content. Pass a string with only the full URL, no need for a final slash `/`."
    args_schema: Type[BaseModel] = BrowserToolSchema
    api_key: str = Field(default=os.environ.get('BROWSERLESS_API_KEY'))
    base_url: str = Field(default="https://browserless.rijsinghani.us/scrape")

    def __init__(self, **data):
        super().__init__(**data)
        if not self.api_key:
            logger.error("BROWSERLESS_API_KEY is not set in the environment variables.")

    def _run(
        self,
        website: str,
        **kwargs: Any,
    ) -> Any:
        """Scrape website content."""
        print(f"Browsing: {website}")
        content = self.get_content(website)
        return f'\nContent of {website}: {content}\n'

    def get_content(self, url: str) -> str:
        payload = {
            "url": url,
            "elements": [{"selector": "body"}]  # Add this line to include the required 'elements' field
        }
        headers = {'cache-control': 'no-cache', 'content-type': 'application/json'}
        try:
            response = requests.post(f"{self.base_url}?token={self.api_key}", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data['data'][0]['results'][0]['html']
            extracted_content = extract(content)
            return extracted_content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch content for {url}: {str(e)}")
            logger.error(f"Response status code: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return ""

    def get_links(self, url: str) -> Set[str]:
        payload = {
            "url": url,
            "elements": [
                {"selector": "a"}
            ]
        }
        headers = {'Cache-Control': 'no-cache', 'Content-Type': 'application/json'}
        try:
            response = requests.post(f"{self.base_url}?token={self.api_key}", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            links = set()
            base_domain = urlparse(url).netloc
            for element in data['data'][0]['results']:
                for attr in element['attributes']:
                    if attr['name'] == 'href':
                        full_url = urljoin(url, attr['value'])
                        if urlparse(full_url).netloc == base_domain:
                            links.add(full_url)
            return links
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch links for {url}: {str(e)}")
            logger.error(f"Response status code: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return set()
