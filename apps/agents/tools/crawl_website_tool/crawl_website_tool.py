import logging
from typing import Optional, Type, Any, List, Set
from pydantic.v1 import BaseModel, Field
from crewai_tools import BaseTool
from urllib.parse import urljoin, urlparse
from apps.agents.tools.browser_tool.browser_tool import BrowserTool

logger = logging.getLogger(__name__)

class FixedCrawlWebsiteToolSchema(BaseModel):
    """Input for CrawlWebsiteTool."""
    pass

class CrawlWebsiteToolSchema(FixedCrawlWebsiteToolSchema):
    """Input for CrawlWebsiteTool."""
    website_url: str = Field(..., description="Mandatory website url to crawl and read content")

class CrawlWebsiteTool(BaseTool):
    name: str = "Crawl and read website content"
    description: str = "A tool that can be used to crawl a website and read its content, including content from internal links on the same page."
    args_schema: Type[BaseModel] = CrawlWebsiteToolSchema
    website_url: Optional[str] = None
    browser_tool: Optional[BrowserTool] = None

    def __init__(self, website_url: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.browser_tool = BrowserTool()
        if website_url is not None:
            self.website_url = website_url
            self.description = f"A tool that can be used to crawl {website_url} and read its content, including content from internal links on the same page."
            self.args_schema = FixedCrawlWebsiteToolSchema

    def _run(self, website_url: str) -> str:
        logger.info(f"Processing {website_url}")
        content = self._crawl_website(website_url)
        return content

    def _crawl_website(self, start_url: str) -> str:
        visited_urls: Set[str] = set()
        urls_to_visit: List[str] = [start_url]
        content = ""
        
        while urls_to_visit:
            url = urls_to_visit.pop(0)
            if url in visited_urls:
                continue
            
            logger.info(f"Processing page: {url}")
            page_content = self.browser_tool.get_content(url)
            content += f"---link: {url}\n{page_content}\n---page-end---\n"
            visited_urls.add(url)
            
            new_links = self.browser_tool.get_links(url)
            for link in new_links:
                if link not in visited_urls and link not in urls_to_visit:
                    urls_to_visit.append(link)
            
            logger.info(f"Processed {url}. Queue size: {len(urls_to_visit)}")
            
            # Limit the number of pages to crawl (adjust as needed)
            if len(visited_urls) >= 10:
                logger.info("Reached maximum number of pages to crawl.")
                break
        
        return content
