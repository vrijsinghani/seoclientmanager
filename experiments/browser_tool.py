import json
import os
from typing import Any, Type, Set

import requests
from pydantic import BaseModel, Field
from trafilatura import extract
from crewai_tools import BaseTool as CrewAIBaseTool
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv

class BrowserToolSchema(BaseModel):
    """Input for BrowserTool."""
    website: str = Field(..., description="Full URL of the website to scrape (e.g., https://google.com)")

class BrowserTool(CrewAIBaseTool):
    name: str = "Scrape website content"
    description: str = "A tool that can be used to scrape website content. Pass a string with only the full URL, no need for a final slash `/`."
    args_schema: Type[BaseModel] = BrowserToolSchema
    api_key: str = Field(default='neuralamibrowserlesstoken')
    base_url: str = Field(default="https://browserless.rijsinghani.us/scrape")

    def __init__(self, **data):
        super().__init__(**data)

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
        payload = json.dumps({"url": url})
        headers = {'cache-control': 'no-cache', 'content-type': 'application/json'}
        response = requests.request("POST", f"{self.base_url}?token={self.api_key}", headers=headers, data=payload)
        if response.status_code == 200:
            content = extract(response.text)
            return content
        else:
            print(f"Failed to fetch content: {response.status_code}")
            return ""

    def get_links(self, url: str) -> Set[str]:
        payload = {
            "url": url,
            "elements": [
                {"selector": "a"}
            ]
        }
        headers = {'Cache-Control': 'no-cache', 'Content-Type': 'application/json'}
        response = requests.post(f"{self.base_url}?token={self.api_key}", headers=headers, json=payload)
        
        if response.status_code == 200:
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
        else:
            print(f"Failed to fetch links: {response.status_code}")
            return set()