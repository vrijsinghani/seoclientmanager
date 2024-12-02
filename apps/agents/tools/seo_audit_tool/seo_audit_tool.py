import json
import os
from typing import Dict, List, Any, Optional, Type, Set
from datetime import datetime
import logging
import asyncio
import aiohttp
import ssl
from collections import defaultdict
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
from pydantic import BaseModel, Field
from crewai_tools import BaseTool
import dotenv
from apps.agents.tools.browser_tool.browser_tool import BrowserTool
from apps.agents.tools.async_crawl_website_tool.async_crawl_website_tool import AsyncCrawlWebsiteTool
from apps.agents.tools.seo_crawler_tool.seo_crawler_tool import SEOCrawlerTool
from apps.common.utils import normalize_url
from apps.agents.utils import URLDeduplicator

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

class SEOAuditToolSchema(BaseModel):
    """Input for SEOAuditTool."""
    website: str = Field(..., title="Website", description="Full URL of the website to perform SEO audit on (e.g., https://example.com)")
    max_pages: int = Field(
        default=100,
        title="Max Pages",
        description="Maximum number of pages to audit"
    )
    check_external_links: bool = Field(
        default=False,
        title="Check External Links",
        description="Whether to check external links for broken links"
    )
    crawl_delay: float = Field(
        default=1.0,
        title="Crawl Delay",
        description="Delay between crawling pages in seconds"
    )

class SEOAuditTool(BaseTool):
    name: str = "SEO Audit Tool"
    description: str = "A tool that performs comprehensive SEO audit on a website, checking for issues like broken links, duplicate content, meta tag issues, and more."
    args_schema: Type[BaseModel] = SEOAuditToolSchema
    tags: Set[str] = {"seo", "audit", "website", "content"}
    api_key: str = Field(default=os.environ.get('BROWSERLESS_API_KEY'))
    browser_tool: BrowserTool = Field(default_factory=BrowserTool)
    crawl_tool: AsyncCrawlWebsiteTool = Field(default_factory=AsyncCrawlWebsiteTool)
    seo_crawler: SEOCrawlerTool = Field(default_factory=SEOCrawlerTool)
    url_deduplicator: URLDeduplicator = Field(default_factory=URLDeduplicator)

    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.api_key:
            logger.error("BROWSERLESS_API_KEY is not set in the environment variables.")
        self._session = None
        self._link_cache = {}  # Global cache for link check results
        self._semaphore = None  # Rate limiting semaphore
        self._checked_urls = set()  # Global set of normalized URLs that have been checked

    def _run(
        self,
        website: str,
        max_pages: int = 100,
        check_external_links: bool = False,
        crawl_delay: float = 1.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run SEO audit."""
        logger.info(f"Starting SEO audit for: {website}")
        start_time = datetime.now()
        
        # Create event loop and run async audit
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._async_audit(website, max_pages, check_external_links, crawl_delay))
            end_time = datetime.now()
            result["summary"]["audit_start_time"] = start_time.isoformat()
            result["summary"]["audit_end_time"] = end_time.isoformat()
            result["summary"]["total_audit_time_seconds"] = (end_time - start_time).total_seconds()
            logger.info(f"SEO audit completed for: {website}")
            return json.loads(json.dumps(result, default=str))  # Ensure JSON serialization
        except Exception as e:
            logger.error(f"Error running SEO audit: {str(e)}")
            raise
        finally:
            loop.close()

    async def _async_audit(
        self,
        website: str,
        max_pages: int = 100,
        check_external_links: bool = False,
        crawl_delay: float = 1.0
    ) -> Dict[str, Any]:
        """Run SEO audit asynchronously."""
        logger.info("Starting crawler...")
        # First, use SEOCrawlerTool to gather detailed page data
        crawler_results = await asyncio.to_thread(
            self.seo_crawler._run,
            website_url=website,
            max_pages=max_pages,
            respect_robots_txt=True,
            crawl_delay=crawl_delay
        )
        logger.info(f"Crawler completed. Found {len(crawler_results.get('pages', []))} pages")

        # Initialize audit results
        audit_results = {
            "broken_links": [],
            "duplicate_content": [],
            "meta_tag_issues": [],
            "ssl_issues": {},
            "sitemap_present": False,
            "robots_txt_present": False,
            "page_analysis": []
        }

        total_links = 0
        all_links = set()  # Track all unique links for broken link checking
        base_domain = urlparse(website).netloc

        logger.info("Processing pages for SEO analysis...")
        # Process crawler results for SEO analysis
        for page in crawler_results.get("pages", []):
            # Create a clean version of the page data for analysis
            page_analysis = await self._analyze_page_seo(page)
            audit_results["page_analysis"].append(page_analysis)
            
            # Collect links for broken link checking
            page_links = page.get("links", [])
            total_links += len(page_links)
            
            # Only check internal links
            for link in page_links:
                if urlparse(link).netloc == base_domain:
                    all_links.add((page["url"], link))  # Store source and target

            # Check for meta tag issues
            meta_issues = []
            
            # Title tag checks
            title = page.get("title", "").strip()
            if not title:
                meta_issues.append({
                    "type": "title",
                    "issue": "Missing title tag",
                    "value": None
                })
            elif len(title) < 10:
                meta_issues.append({
                    "type": "title",
                    "issue": f"Title tag too short ({len(title)} chars)",
                    "value": title
                })
            elif len(title) > 60:
                meta_issues.append({
                    "type": "title",
                    "issue": f"Title tag too long ({len(title)} chars)",
                    "value": title
                })
            
            # Meta description checks
            meta_desc = page.get("meta_description", "").strip()
            if not meta_desc:
                meta_issues.append({
                    "type": "meta_description",
                    "issue": "Missing meta description",
                    "value": None
                })
            elif len(meta_desc) < 50:
                meta_issues.append({
                    "type": "meta_description",
                    "issue": f"Meta description too short ({len(meta_desc)} chars)",
                    "value": meta_desc
                })
            elif len(meta_desc) > 160:
                meta_issues.append({
                    "type": "meta_description",
                    "issue": f"Meta description too long ({len(meta_desc)} chars)",
                    "value": meta_desc
                })
            
            # Meta keywords check
            meta_keywords = page.get("meta_keywords", [])
            if not meta_keywords:
                meta_issues.append({
                    "type": "meta_keywords",
                    "issue": "Missing meta keywords",
                    "value": None
                })
            elif len(meta_keywords) < 3:
                meta_issues.append({
                    "type": "meta_keywords",
                    "issue": f"Too few meta keywords ({len(meta_keywords)})",
                    "value": meta_keywords
                })
            elif len(meta_keywords) > 10:
                meta_issues.append({
                    "type": "meta_keywords",
                    "issue": f"Too many meta keywords ({len(meta_keywords)})",
                    "value": meta_keywords
                })
            
            # H1 tag checks
            h1_tags = page.get("h1_tags", [])
            if not h1_tags:
                meta_issues.append({
                    "type": "h1",
                    "issue": "Missing H1 tag",
                    "value": None
                })
            elif len(h1_tags) > 1:
                meta_issues.append({
                    "type": "h1",
                    "issue": f"Multiple H1 tags ({len(h1_tags)})",
                    "value": h1_tags
                })
            
            if meta_issues:
                audit_results["meta_tag_issues"].append({
                    "url": page["url"],
                    "issues": meta_issues
                })
        logger.info("Page analysis completed")

        logger.info("Checking for broken links...")
        # Check for broken internal links
        await self._check_broken_links(all_links, audit_results)
        logger.info(f"Found {len(audit_results['broken_links'])} broken links")
        
        logger.info("Checking for duplicate content...")
        # Check for duplicate content using the full content but not including it in results
        await self._check_duplicate_content(crawler_results.get("pages", []), audit_results)
        logger.info(f"Found {len(audit_results['duplicate_content'])} duplicate content issues")
        
        logger.info("Checking SSL...")
        # Check SSL
        await self._check_ssl(website, audit_results)
        
        logger.info("Checking robots.txt and sitemap...")
        # Check robots.txt and sitemap
        await self._check_robots_sitemap(website, audit_results)

        # Add summary stats from crawler
        audit_results["summary"] = {
            "total_pages": crawler_results["total_pages"],
            "total_links": total_links,
            "total_meta_issues": len(audit_results["meta_tag_issues"]),
            "total_broken_links": len(audit_results["broken_links"]),
            "crawl_time_seconds": crawler_results["crawl_time_seconds"],
            "start_time": crawler_results["start_time"],
            "end_time": crawler_results["end_time"]
        }

        logger.info("SEO audit completed successfully")
        return audit_results

    async def _analyze_page_seo(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze SEO aspects of a single page."""
        return {
            "url": page["url"],
            "title_length": len(page.get("title", "")),
            "meta_description_length": len(page.get("meta_description", "")),
            "h1_count": len(page.get("h1_tags", [])),
            "outbound_links": len(page.get("links", [])),
            "content_length": len(page.get("text_content", "")),
            "timestamp": page.get("crawl_timestamp")
        }

    async def _check_duplicate_content(self, pages: List[Dict[str, Any]], audit_results: Dict[str, Any]):
        """Check for duplicate content across pages."""
        duplicates = []
        content_hash_map = defaultdict(list)

        for page in pages:
            url = page['url']
            content = page.get('content', '')
            
            # Use URLDeduplicator's content check
            if self.url_deduplicator.fallback_content_check(url, content):
                normalized_url = self.url_deduplicator._normalize_url(url)
                content_hash = self.url_deduplicator._hash_main_content(content)
                if normalized_url not in content_hash_map[content_hash]:
                    content_hash_map[content_hash].append(normalized_url)
        
        for urls in content_hash_map.values():
            if len(urls) > 1:  # Only report if we have actual duplicates (different URLs)
                # Sort URLs for consistent output
                sorted_urls = sorted(urls)
                audit_results["duplicate_content"].append({
                    "urls": sorted_urls,
                    "timestamp": datetime.now().isoformat()
                })

    async def _check_ssl(self, website: str, audit_results: Dict[str, Any]):
        """Check SSL certificate validity."""
        try:
            context = ssl.create_default_context()
            async with aiohttp.TCPConnector(ssl=context) as connector:
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(f"https://{website}") as response:
                        audit_results["ssl_issues"] = {"valid_certificate": response.status == 200}
        except Exception:
            audit_results["ssl_issues"] = {"valid_certificate": False}

    async def _check_robots_sitemap(self, website: str, audit_results: Dict[str, Any]):
        """Check for robots.txt and sitemap.xml."""
        async with aiohttp.ClientSession() as session:
            # Check robots.txt
            try:
                async with session.get(f"https://{website}/robots.txt") as response:
                    audit_results["robots_txt_present"] = response.status == 200
            except Exception:
                audit_results["robots_txt_present"] = False
            
            # Check sitemap.xml
            try:
                async with session.get(f"https://{website}/sitemap.xml") as response:
                    audit_results["sitemap_present"] = response.status == 200
            except Exception:
                audit_results["sitemap_present"] = False

    async def _check_broken_links(self, links: Set[tuple], audit_results: Dict[str, Any]):
        """Check for broken internal links using HEAD requests."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            semaphore = asyncio.Semaphore(5)  # Allow more concurrent requests since HEAD is lightweight
            
            async def check_link(source_url: str, target_url: str):
                """Check if a link is broken using HEAD request."""
                async with semaphore:
                    max_retries = 3
                    retry_count = 0
                    
                    while retry_count < max_retries:
                        try:
                            # Try HEAD first
                            try:
                                async with session.head(target_url, allow_redirects=True, timeout=5) as response:
                                    if response.status >= 400:
                                        # If HEAD fails, try GET as some servers might not support HEAD
                                        async with session.get(target_url, allow_redirects=True, timeout=5) as get_response:
                                            if get_response.status >= 400:
                                                audit_results["broken_links"].append({
                                                    "source_url": source_url,
                                                    "target_url": target_url,
                                                    "status_code": get_response.status,
                                                    "error": f"HTTP {get_response.status}",
                                                    "timestamp": datetime.now().isoformat()
                                                })
                                            return
                                    return
                            except aiohttp.ClientError as client_err:
                                # If HEAD fails with client error, try GET
                                try:
                                    async with session.get(target_url, allow_redirects=True, timeout=5) as response:
                                        if response.status >= 400:
                                            audit_results["broken_links"].append({
                                                "source_url": source_url,
                                                "target_url": target_url,
                                                "status_code": response.status,
                                                "error": f"HTTP {response.status}",
                                                "timestamp": datetime.now().isoformat()
                                            })
                                        return
                                except aiohttp.ClientError as get_err:
                                    raise get_err
                            return  # Success, exit retry loop
                            
                        except asyncio.TimeoutError:
                            retry_count += 1
                            if retry_count == max_retries:
                                audit_results["broken_links"].append({
                                    "source_url": source_url,
                                    "target_url": target_url,
                                    "status_code": None,
                                    "error": f"Timeout after {max_retries} retries",
                                    "timestamp": datetime.now().isoformat()
                                })
                            else:
                                await asyncio.sleep(1)  # Wait before retrying
                                continue
                                
                        except Exception as e:
                            audit_results["broken_links"].append({
                                "source_url": source_url,
                                "target_url": target_url,
                                "status_code": None,
                                "error": str(e),
                                "timestamp": datetime.now().isoformat()
                            })
                            return
            tasks = []
            for source_url, target_url in links:
                tasks.append(asyncio.create_task(check_link(source_url, target_url)))
            
            # Wait for all checks to complete
            if tasks:
                await asyncio.gather(*tasks)

    def _generate_report(self, audit_results: Dict[str, Any]) -> Dict[str, Any]:
        """Format the audit results into a detailed report."""
        total_meta_issues = len(audit_results["meta_tag_issues"])
        
        report = {
            "summary": {
                "total_pages": audit_results["summary"]["total_pages"],
                "total_issues": len(audit_results["broken_links"]) + 
                              len(audit_results["duplicate_content"]) + 
                              total_meta_issues,
                "timestamp": datetime.now().isoformat()
            },
            "issues": {
                "broken_links": audit_results["broken_links"],
                "duplicate_content": audit_results["duplicate_content"],
                "meta_tag_issues": audit_results["meta_tag_issues"]
            },
            "technical": {
                "ssl": audit_results["ssl_issues"],
                "sitemap": audit_results["sitemap_present"],
                "robots_txt": audit_results["robots_txt_present"]
            },
            "crawl_stats": {
                "total_pages": audit_results["summary"]["total_pages"],
                "total_links": audit_results["summary"]["total_links"],
                "crawl_time": audit_results["summary"]["crawl_time_seconds"]
            },
            "page_analysis": audit_results["page_analysis"]
        }
        
        return report
