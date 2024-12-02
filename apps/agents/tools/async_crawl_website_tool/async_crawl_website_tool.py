import asyncio
from typing import Optional, Type, List, Dict, Any
from pydantic import BaseModel, Field
from crewai_tools import BaseTool
from urllib.parse import urlparse
from trafilatura import extract
from celery import shared_task
from celery.contrib.abortable import AbortableTask
from django.contrib.auth.models import User
from django.conf import settings
import logging
import os
import re
from apps.crawl_website.models import CrawlResult
from spider_rs import Website, Page
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class AsyncCrawlWebsiteToolSchema(BaseModel):
    """Input for AsyncCrawlWebsiteTool."""
    website_url: str = Field(..., description="Mandatory website URL to crawl and read content")
    max_pages: int = Field(default=100, description="Maximum number of pages to crawl")

class AsyncCrawlWebsiteTool(BaseTool):
    name: str = "Async Crawl and Read Website Content"
    description: str = "An asynchronous tool that can crawl a website and read its content, including content from internal links on the same page."
    args_schema: Type[BaseModel] = AsyncCrawlWebsiteToolSchema
    website_url: Optional[str] = None
    max_pages: int = 100

    def __init__(self, website_url: Optional[str] = None, max_pages: int = 100, **kwargs):
        super().__init__(**kwargs)
        self.max_pages = max_pages
        if website_url:
            self.website_url = website_url
            self.description = f"An asynchronous tool to crawl {website_url} and read its content, including content from internal links."

    async def _run(self, website_url: str = None, max_pages: int = None) -> dict:
        url = website_url or self.website_url
        if not url:
            raise ValueError("No website URL provided")
        
        self.max_pages = max_pages or self.max_pages
        logger.info(f"Starting crawl for URL: {url} with max_pages: {self.max_pages}")
        
        try:
            result = await self.crawl_website(url)
            logger.info(f"Crawl completed. Total links: {result['total_links']}, Links visited: {len(result['links_visited'])}")
            return result
        except Exception as e:
            logger.error(f"Error during crawl: {e}")
            raise

    async def crawl_website(self, url: str) -> Dict[str, Any]:
        website = Website(url)
        website.with_budget({"*": self.max_pages})  # Limit to max_pages
        website.with_respect_robots_txt(True)
        website.with_subdomains(False)  # Stick to the main domain
        website.with_tld(False)  # Don't crawl top-level domain
        website.with_delay(1)  # Be respectful with a 1-second delay between requests

        pages_queue = asyncio.Queue()
        total_links = 0
        links_visited = set()
        content = ""
        
        # Use scrape() instead of crawl() for consistency with sync version
        with ThreadPoolExecutor() as executor:
            future = executor.submit(website.scrape)
            future.result()  # Wait for scrape to complete
            
        pages = website.get_pages()
        total_links = len(pages)
        
        # Limit pages to max_pages
        pages = list(pages)[:self.max_pages]
        logger.info(f"Limited pages to {len(pages)} out of {total_links} total links")
        
        # Process pages concurrently
        async def process_page(page: Page):
            try:
                logger.info(f"Processing page: {page.url}")
                page_content = await self._extract_content(page)
                if page_content:  # Only add to visited if we got content
                    links_visited.add(page.url)
                    return page_content
                return ""
            except Exception as e:
                logger.error(f"Error processing page {page.url}: {e}")
                return ""

        # Process all pages concurrently with semaphore
        semaphore = asyncio.Semaphore(10)
        async def bounded_process_page(page: Page):
            async with semaphore:
                return await process_page(page)

        # Process all pages
        results = await asyncio.gather(*[bounded_process_page(page) for page in pages])
        content = "".join(results)

        logger.info(f"Crawl finished. Total links: {total_links}, Links visited: {len(links_visited)}")

        return {
            "content": content,
            "links_visited": list(links_visited),
            "total_links": total_links,
            "links_to_visit": list(set(page.url for page in pages) - links_visited)
        }

    async def _extract_content(self, page: Page) -> str:
        try:
            html_content = page.content
            extracted_content = extract(html_content)
            logger.info(f"Extracted content length for {page.url}: {len(extracted_content) if extracted_content else 0}")
            return f"---link: {page.url}\n{extracted_content}\n---page-end---\n" if extracted_content else ""
        except Exception as e:
            logger.error(f"Error extracting content from {page.url}: {e}")
            return ""

    @staticmethod
    def _get_relative_path(url: str) -> str:
        parsed_url = urlparse(url)
        # Include both path and query parameters for WordPress URLs
        if parsed_url.query:
            return f"{parsed_url.path}?{parsed_url.query}"
        return parsed_url.path or '/'

def sanitize_url(url: str) -> str:
    """Sanitize the URL to create a valid folder name."""
    url = re.sub(r'^https?://(www\.)?', '', url)
    return re.sub(r'[^a-zA-Z0-9]', '_', url)

def save_crawl_result(user_id: int, website_url: str, content: str, links_visited: List[str], total_links: int, links_to_visit: List[str]) -> str:
    """Save the crawl result to a file in the user's directory."""
    sanitized_url = sanitize_url(website_url)
    user_dir = os.path.join(settings.MEDIA_ROOT, f'{user_id}', 'Crawled Websites')
    result_dir = os.path.join(user_dir, sanitized_url)
    os.makedirs(result_dir, exist_ok=True)

    file_path = os.path.join(result_dir, f'{sanitized_url}--content.txt')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(f"Website URL: {website_url}\n\n")
        f.write(f"Links Visited:\n{', '.join(links_visited)}\n\n")
        f.write(f"Total Links: {total_links}\n\n")
        f.write("Content:\n")
        f.write(content)

    return file_path

@shared_task(bind=True, base=AbortableTask)
def crawl_website_task(self, website_url: str, user_id: int, max_pages: int = 100):
    logger.info(f"Starting crawl_website_task for URL: {website_url}")
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
        return None

    async_tool = AsyncCrawlWebsiteTool(website_url=website_url, max_pages=max_pages)
    
    async def run_crawl():
        return await async_tool._run(website_url)

    try:
        result = asyncio.run(run_crawl())
        logger.info(f"Crawl completed. Total links: {result['total_links']}, Links visited: {len(result['links_visited'])}")
    except Exception as e:
        logger.error(f"Error during crawl: {e}")
        return None

    file_path = save_crawl_result(
        user_id,
        website_url,
        result["content"],
        result["links_visited"],
        result["total_links"],
        result["links_to_visit"]
    )

    crawl_result = CrawlResult.objects.create(
        user=user,
        website_url=website_url,
        content=result["content"],
        links_visited=result["links_visited"],
        total_links=result["total_links"],
        links_to_visit=result["links_to_visit"],
        result_file_path=file_path
    )
    
    logger.info(f"Crawl task completed for URL: {website_url}")
    return crawl_result.id
