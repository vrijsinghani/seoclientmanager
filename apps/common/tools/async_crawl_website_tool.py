import asyncio
import aiohttp
from typing import Optional, Type, Any, List
from pydantic import BaseModel, Field
from crewai_tools import BaseTool
from urllib.parse import urlparse
from trafilatura import extract, sitemaps, spider
from celery import shared_task
from celery.contrib.abortable import AbortableTask
from django.contrib.auth.models import User
from django.conf import settings
import logging
import os
import re
from apps.crawl_website.models import CrawlResult

logger = logging.getLogger(__name__)

class FixedCrawlWebsiteToolSchema(BaseModel):
  """Input for AsyncCrawlWebsiteTool."""
  pass

class AsyncCrawlWebsiteToolSchema(FixedCrawlWebsiteToolSchema):
  """Input for AsyncCrawlWebsiteTool."""
  website_url: str = Field(..., description="Mandatory website URL to crawl and read content")

class AsyncCrawlWebsiteTool(BaseTool):
  name: str = "Async Crawl and Read Website Content"
  description: str = "An asynchronous tool that can crawl a website and read its content, including content from internal links on the same page."
  args_schema: Type[BaseModel] = AsyncCrawlWebsiteToolSchema
  website_url: Optional[str] = None
  headers: dict = {
      'User-Agent': 'Mozilla/5.0',
      'Accept-Language': 'en-US,en;q=0.5',
  }

  def __init__(self, website_url: Optional[str] = None, **kwargs):
      super().__init__(**kwargs)
      if website_url is not None:
          self.website_url = website_url
          self.description = f"An asynchronous tool to crawl {website_url} and read its content, including content from internal links."
          self.args_schema = FixedCrawlWebsiteToolSchema

  async def _run(self, website_url: str = None) -> dict:
      """
      Implement the _run method required by BaseTool.
      This method will be called when the tool is executed.
      """
      url = website_url or self.website_url
      if not url:
          raise ValueError("No website URL provided")

      content = ""
      links_visited = []
      total_links = 0
      links_to_visit = []

      async for current, total, visited, current_content, to_visit in self.crawl_website(url):
          content = current_content
          links_visited = visited
          total_links = total
          links_to_visit = to_visit

      return {
          "content": content,
          "links_visited": links_visited,
          "total_links": total_links,
          "links_to_visit": links_to_visit
      }

  async def crawl_website(self, url: str):
      links_to_visit = await self._get_links_to_visit(url)
      total_links = len(links_to_visit)
      content = ""
      links_visited = []
      logger.info(f"Reading {total_links} pages.")

      async with aiohttp.ClientSession(headers=self.headers) as session:
          for i, link in enumerate(links_to_visit):
              page_content = await self._fetch_and_extract_content(session, link)
              content += page_content or ""
              links_visited.append(self._get_relative_path(link))
              # Yield progress after each page is processed
              yield i + 1, total_links, links_visited, content, links_to_visit

  async def _get_links_to_visit(self, url: str) -> List[str]:
      sitemap_links = await self._sitemap_search(url)
      if sitemap_links:
          logger.info(f"Found {len(sitemap_links)} pages from sitemap.")
          return sitemap_links
      else:
          known_urls = await self._focused_crawler(url)
          logger.info(f"Found {len(known_urls)} pages from crawling the website.")
          return list(known_urls)

  async def _sitemap_search(self, url: str) -> List[str]:
      loop = asyncio.get_event_loop()
      return await loop.run_in_executor(None, sitemaps.sitemap_search, url)

  async def _focused_crawler(self, url: str) -> List[str]:
      loop = asyncio.get_event_loop()
      _, known_urls = await loop.run_in_executor(None, spider.focused_crawler, url, 10, 1000)
      return known_urls

  async def _fetch_and_extract_content(self, session: aiohttp.ClientSession, url: str) -> str:
      try:
          async with session.get(url) as response:
              if response.status == 200:
                  html_content = await response.text()
                  if html_content:
                      loop = asyncio.get_event_loop()
                      extracted_content = await loop.run_in_executor(None, extract, html_content, url)
                      return f"---link: {url}\n{extracted_content}\n---page-end---\n" if extracted_content else ""
              else:
                  logger.warning(f"Failed to fetch {url}: status {response.status}")
                  return ""
      except Exception as e:
          logger.error(f"Error fetching {url}: {e}")
          return ""

  def _get_relative_path(self, url: str) -> str:
      parsed_url = urlparse(url)
      return parsed_url.path or '/'

def sanitize_url(url: str) -> str:
    """Sanitize the URL to create a valid folder name."""
    # Remove protocol and www
    url = re.sub(r'^https?://(www\.)?', '', url)
    # Replace non-alphanumeric characters with underscores
    return re.sub(r'[^a-zA-Z0-9]', '_', url)

def save_crawl_result(user_id: int, website_url: str, content: str, links_visited: List[str], total_links: int, links_to_visit: List[str]) -> str:
    """Save the crawl result to a file in the user's directory."""
    sanitized_url = sanitize_url(website_url)
    user_dir = os.path.join(settings.MEDIA_ROOT, f'{user_id}', 'Crawled Websites')
    result_dir = os.path.join(user_dir, sanitized_url)
    os.makedirs(result_dir, exist_ok=True)

    file_path = os.path.join(result_dir, f'{sanitized_url}--content.txt')
    with open(file_path, 'w') as f:
        f.write(f"Website URL: {website_url}\n\n")
        f.write(f"Links Visited:\n{', '.join(links_visited)}\n\n")
        f.write(f"Total Links: {total_links}\n\n")
        f.write("Content:\n")
        f.write(content)

    return file_path

@shared_task(bind=True, base=AbortableTask)
def crawl_website_task(self, website_url: str, user_id: int):
    logger.info(f"Starting crawl_website_task for URL: {website_url}")
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
        return None

    async_tool = AsyncCrawlWebsiteTool(website_url=website_url)
    
    async def run_crawl():
        return await async_tool._run(website_url)

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(run_crawl())

    # Save the result to a file
    file_path = save_crawl_result(
        user_id,
        website_url,
        result["content"],
        result["links_visited"],
        result["total_links"],
        result["links_to_visit"]
    )

    # Create the CrawlResult object
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