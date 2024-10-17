import logging
from typing import Optional, Type, Any, List, Set
from pydantic.v1 import BaseModel, Field
from crewai_tools import BaseTool
from urllib.parse import urljoin, urlparse
from spider_rs import Website, Page
from trafilatura import extract


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

    def __init__(self, website_url: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        if website_url is not None:
            self.website_url = website_url
            self.description = f"A tool that can be used to crawl {website_url} and read its content, including content from internal links on the same page."
            self.args_schema = FixedCrawlWebsiteToolSchema

    def _run(self, website_url: str) -> str:
        url = website_url or self.website_url
        if not url:
            raise ValueError("No website URL provided")

        logger.info(f"Starting crawl for URL: {url}")
        
        try:
            result = self._crawl_website(url)  # Changed website_url to url
            # Remove the log statement that was causing the error
            return result
        except Exception as e:
            logger.error(f"Error during crawl: {e}")
            raise

    def _crawl_website(self, start_url: str) -> str:  # Changed return type to str
        website = Website(start_url)
        website.with_budget({"*": 100})  # Set a limit for crawling
        website.with_respect_robots_txt(True)
        website.with_subdomains(False)  # Stick to the main domain
        website.with_tld(False)  # Don't crawl top-level domain
        website.with_delay(1)  # Be respectful with a 1-second delay between requests
        content = ""

        website.scrape()
        
        pages = website.get_pages()
        
        for page in pages:
            page_content = self._extract_content(page)
            content += page_content
        
        return content  # Return the content directly

    def _extract_content(self, page: Page) -> str:
        try:
            html_content = page.content
            extracted_content = extract(html_content)
            logger.info(f"Extracted content length for {page.url}: {len(extracted_content) if extracted_content else 0}")
            return f"---link: {page.url}\n{extracted_content}\n---page-end---\n" if extracted_content else ""
        except Exception as e:
            logger.error(f"Error extracting content from {page.url}: {e}")
            return ""
