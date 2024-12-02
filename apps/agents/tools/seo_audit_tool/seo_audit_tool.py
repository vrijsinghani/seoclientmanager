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

class SEOAuditTool(BaseTool):
    name: str = "SEO Audit Tool"
    description: str = "A tool that performs comprehensive SEO audit on a website, checking for issues like broken links, duplicate content, meta tag issues, and more."
    args_schema: Type[BaseModel] = SEOAuditToolSchema
    tags: Set[str] = {"seo", "audit", "website", "content"}
    api_key: str = Field(default=os.environ.get('BROWSERLESS_API_KEY'))
    browser_tool: BrowserTool = Field(default_factory=BrowserTool)
    crawl_tool: AsyncCrawlWebsiteTool = Field(default_factory=AsyncCrawlWebsiteTool)

    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.api_key:
            logger.error("BROWSERLESS_API_KEY is not set in the environment variables.")
        self._session = None
        self._link_cache = {}  # Global cache for link check results
        self._semaphore = None  # Rate limiting semaphore
        self._checked_urls = set()  # Global set of normalized URLs that have been checked

    async def _create_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _cleanup(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _run(
        self,
        website: str,
        max_pages: int = 100,
        check_external_links: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run SEO audit."""
        logger.info(f"Starting SEO audit for: {website}")
        
        # Create event loop and run async audit
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._async_audit(website, max_pages, check_external_links))
            return result
        except Exception as e:
            logger.error(f"Error running SEO audit: {str(e)}")
            raise
        finally:
            loop.close()

    async def _async_audit(
        self,
        website: str,
        max_pages: int = 100,
        check_external_links: bool = False
    ) -> Dict[str, Any]:
        """Run SEO audit asynchronously."""
        audit_results = {
            "broken_links": [],
            "duplicate_content": [],
            "meta_tag_issues": [],
            "ssl_issues": {},
            "sitemap_present": False,
            "robots_txt_present": False,
            "mobile_friendly": True,
            "page_speed_issues": {},
            "crawl_stats": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Create client session with timeout
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes total timeout
            async with aiohttp.ClientSession(timeout=timeout) as self._session:
                # Step 1: Crawl website with timeout
                try:
                    crawl_result = await asyncio.wait_for(
                        self.crawl_tool._run(website, max_pages=max_pages),
                        timeout=180  # 3 minutes timeout for crawl
                    )
                except asyncio.TimeoutError:
                    logger.error("Crawl operation timed out")
                    raise
                
                # Convert crawl results to page objects
                pages = []
                visited_urls = set()
                
                # Process crawl results in chunks to avoid memory issues
                crawl_pages = []
                for page in crawl_result.get('content', '').split('---link: '):
                    if not page.strip():
                        continue
                    url_end = page.find('\n')
                    if url_end != -1:
                        url = page[:url_end].strip()
                        content = page[url_end:].split('---page-end---')[0].strip()
                        crawl_pages.append({'url': url, 'content': content})
                
                logger.info(f"Found {len(crawl_pages)} pages to audit")
                
                # Process pages in smaller chunks
                chunk_size = 5
                for i in range(0, len(crawl_pages), chunk_size):
                    chunk = crawl_pages[i:i + chunk_size]
                    chunk_tasks = []
                    
                    for page in chunk:
                        url = page['url']
                        if url in visited_urls:
                            continue
                        visited_urls.add(url)
                        
                        try:
                            # Get page content with timeout
                            content = await asyncio.wait_for(
                                asyncio.to_thread(self.browser_tool._run, url, output_type="raw"),
                                timeout=30  # 30 seconds timeout per page
                            )
                            if content:
                                pages.append({
                                    'url': url,
                                    'content': content if isinstance(content, str) else str(content),
                                    'status_code': 200
                                })
                        except (asyncio.TimeoutError, Exception) as e:
                            logger.error(f"Error fetching content for {url}: {str(e)}")
                            continue
                    
                    # Process chunk of pages
                    if pages:
                        tasks = []
                        for page in pages[-chunk_size:]:  # Process only the new chunk
                            tasks.append(self._process_page(page, audit_results, check_external_links))
                        
                        try:
                            await asyncio.wait_for(
                                asyncio.gather(*tasks),
                                timeout=60  # 1 minute timeout for processing chunk
                            )
                        except asyncio.TimeoutError:
                            logger.error(f"Timeout processing chunk of pages")
                            continue
                
                if not pages:
                    raise ValueError("No pages found to audit")

                # Update crawl stats
                audit_results["crawl_stats"] = {
                    "total_pages": len(pages),
                    "total_links": crawl_result.get('total_links', 0),
                    "crawl_time": crawl_result.get('crawl_time', 0)
                }
                
                # Final steps with timeouts
                try:
                    await asyncio.wait_for(
                        self._check_basic_requirements(website, audit_results),
                        timeout=30
                    )
                except asyncio.TimeoutError:
                    logger.error("Timeout checking basic requirements")
                
                try:
                    await asyncio.wait_for(
                        self._analyze_duplicate_content(pages, audit_results),
                        timeout=60
                    )
                except asyncio.TimeoutError:
                    logger.error("Timeout analyzing duplicate content")
                
                logger.info("SEO audit completed successfully")
                return self._generate_report(audit_results)

        except Exception as e:
            logger.error(f"Error during SEO audit: {e}")
            # Return partial results if available
            if audit_results["crawl_stats"]:
                logger.info("Returning partial results due to error")
                return self._generate_report(audit_results)
            raise
        finally:
            await self._cleanup()

    async def _check_basic_requirements(self, url: str, audit_results: Dict[str, Any]):
        """Check basic SEO requirements."""
        try:
            # Check SSL
            parsed_url = urlparse(url)
            ssl_valid = await self._check_ssl(parsed_url.netloc)
            audit_results["ssl_issues"] = {"valid_certificate": ssl_valid}

            # Check sitemap
            sitemap_url = urljoin(url, '/sitemap.xml')
            async with self._session.get(sitemap_url) as response:
                audit_results["sitemap_present"] = response.status == 200

            # Check robots.txt
            robots_url = urljoin(url, '/robots.txt')
            async with self._session.get(robots_url) as response:
                audit_results["robots_txt_present"] = response.status == 200

        except Exception as e:
            logger.error(f"Error checking basic requirements: {e}")

    async def _check_ssl(self, hostname: str) -> bool:
        """Check SSL certificate validity."""
        try:
            context = ssl.create_default_context()
            async with aiohttp.TCPConnector(ssl=context) as connector:
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(f"https://{hostname}") as response:
                        return True
        except Exception:
            return False

    async def _process_page(self, page: Dict[str, Any], audit_results: Dict[str, Any], check_external_links: bool):
        """Process a single page for SEO issues."""
        url = page.get('url')
        content = page.get('content')
        
        if not url or not content:
            logger.debug(f"Skipping page {url} - missing content")
            return

        logger.debug(f"Processing page {url}")
        
        try:
            # Ensure content is a string
            if not isinstance(content, str):
                content = str(content)
            
            # Remove any prefix text that might have been added
            content_start = content.find('<!DOCTYPE')
            if content_start != -1:
                content = content[content_start:]
            else:
                content_start = content.find('<html')
                if content_start != -1:
                    content = content[content_start:]
            
            # Parse with lxml for better HTML handling
            soup = BeautifulSoup(content, 'lxml', from_encoding='utf-8')
            
            # Ensure we have a head section
            if not soup.head and soup.html:
                head = soup.new_tag('head')
                soup.html.insert(0, head)
                        
        except Exception as e:
            logger.error(f"Error parsing HTML for {url}: {e}")
            return

        # Check meta tags
        meta_issues = self._check_meta_tags(soup, url)
        if meta_issues:
            audit_results["meta_tag_issues"].append(meta_issues)
        
        # Check broken links
        await self._check_broken_links(url, soup, audit_results, check_external_links)

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to avoid checking the same URL in different forms."""
        parsed = urlparse(url)
        # Remove trailing slashes
        path = parsed.path.rstrip('/')
        # Sort query parameters
        query = '&'.join(sorted(parsed.query.split('&'))) if parsed.query else ''
        # Remove fragment
        fragment = ''
        # Reconstruct URL
        return urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            path,
            parsed.params,
            query,
            fragment
        ))

    async def _check_broken_links(self, url: str, soup: BeautifulSoup, audit_results: Dict[str, Any], check_external_links: bool):
        """Check for broken links."""
        if self._semaphore is None:
            # Initialize rate limiting semaphore - allow 10 concurrent requests
            self._semaphore = asyncio.Semaphore(10)
        
        links = soup.find_all('a', href=True)
        tasks = []
        
        # Get base domain for internal link checking
        base_domain = urlparse(url).netloc
        logger.debug(f"Checking links on page: {url} (base domain: {base_domain})")
        
        # Process each link only once
        for link in links:
            href = link['href']
            
            # Skip certain link types and fragments immediately
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#', 'data:', 'file:', 'about:')):
                continue
                
            full_url = urljoin(url, href)
            parsed = urlparse(full_url)
            
            # Normalize URL first
            normalized_url = self._normalize_url(full_url)
            
            # Skip if already processed
            if normalized_url in self._checked_urls:
                continue
                
            # Skip external links if check_external_links is False
            if not check_external_links and parsed.netloc != base_domain:
                self._checked_urls.add(normalized_url)  # Add to checked set to avoid future processing
                continue
                
            # For internal links, ensure we're using HTTPS
            if parsed.netloc == base_domain and parsed.scheme == 'http':
                full_url = 'https://' + full_url[7:]  # Replace http:// with https://
                
            # Add to checked set and create task
            self._checked_urls.add(normalized_url)
            logger.debug(f"Checking unique link: {full_url}")
            tasks.append(self._check_link(url, full_url))
        
        # Process links in parallel with bounded concurrency
        if tasks:
            results = await asyncio.gather(*tasks)
            broken_links = [r for r in results if r]
            if broken_links:
                logger.debug(f"Found {len(broken_links)} broken links on {url}")
                for broken in broken_links:
                    logger.debug(f"Broken link: {broken['broken_link']} (Status: {broken['status_code']})")
            audit_results["broken_links"].extend(broken_links)

    async def _check_link(self, source_url: str, link_url: str) -> Optional[Dict[str, Any]]:
        """Check if a link is broken."""
        normalized_url = self._normalize_url(link_url)
        
        # Check cache first
        if normalized_url in self._link_cache:
            logger.debug(f"Using cached result for {link_url}")
            cached_result = self._link_cache[normalized_url]
            if cached_result is None:
                return None
            return {
                "source_page": source_url,
                **cached_result
            }

        try:
            # Configure timeout and headers with more realistic values
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            # Use semaphore for rate limiting
            async with self._semaphore:
                # Try HEAD request first for efficiency
                try:
                    async with self._session.head(
                        link_url, 
                        allow_redirects=True, 
                        timeout=timeout,
                        headers=headers,
                        verify_ssl=False
                    ) as response:
                        status = response.status
                        final_url = str(response.url)
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    # If HEAD fails, try GET as fallback
                    async with self._session.get(
                        link_url, 
                        allow_redirects=True, 
                        timeout=timeout,
                        headers=headers,
                        verify_ssl=False
                    ) as response:
                        status = response.status
                        final_url = str(response.url)
                
                logger.debug(f"Link check result - URL: {link_url}, Status: {status}, Final URL: {final_url}")
                
                # Consider various success scenarios
                if status == 200:
                    self._link_cache[normalized_url] = None
                    return None

                if status in [301, 302, 307, 308]:
                    normalized_final = self._normalize_url(final_url)
                    # Check various redirect scenarios
                    if any([
                        # HTTP to HTTPS redirect
                        (link_url.startswith('http://') and final_url.startswith('https://')),
                        # Same URL without trailing slash or normalized
                        (normalized_url == normalized_final),
                        # WWW version redirect
                        (link_url.replace('://', '://www.') == final_url or 
                         final_url.replace('://', '://www.') == link_url)
                    ]):
                        self._link_cache[normalized_url] = None
                        return None
                
                if status >= 400:
                    result = {
                        "broken_link": link_url,
                        "status_code": status
                    }
                    self._link_cache[normalized_url] = result
                    return {
                        "source_page": source_url,
                        **result
                    }
                
                self._link_cache[normalized_url] = None
                return None
                
        except asyncio.TimeoutError:
            logger.debug(f"Timeout checking link: {link_url}")
            result = {
                "broken_link": link_url,
                "status_code": 0,
                "error": "Timeout"
            }
            self._link_cache[normalized_url] = result
            return {
                "source_page": source_url,
                **result
            }
        except Exception as e:
            logger.debug(f"Error checking link {link_url}: {str(e)}")
            result = {
                "broken_link": link_url,
                "status_code": 0,
                "error": str(e)
            }
            self._link_cache[normalized_url] = result
            return {
                "source_page": source_url,
                **result
            }

    def _check_meta_tags(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Check meta tags for SEO issues."""
        issues = {
            "missing_meta": [],
            "duplicate_meta": [],
            "meta_length_issues": []
        }
        
        # Check title
        titles = soup.find_all('title')
        if not titles:
            issues["missing_meta"].append({"tag": "title", "url": url})
        elif len(titles) > 1:
            issues["duplicate_meta"].append({"tag": "title", "url": url})
        else:
            title_text = titles[0].get_text()
            if len(title_text) < 10 or len(title_text) > 60:
                issues["meta_length_issues"].append({
                    "tag": "title",
                    "content": title_text,
                    "length": len(title_text),
                    "url": url
                })
        
        # Check meta description
        descriptions = soup.find_all('meta', attrs={"name": "description"})
        if not descriptions:
            issues["missing_meta"].append({"tag": "meta description", "url": url})
        elif len(descriptions) > 1:
            issues["duplicate_meta"].append({"tag": "meta description", "url": url})
        else:
            desc_content = descriptions[0].get('content', '')
            if len(desc_content) < 50 or len(desc_content) > 160:
                issues["meta_length_issues"].append({
                    "tag": "meta description",
                    "content": desc_content,
                    "length": len(desc_content),
                    "url": url
                })
        
        # Check meta keywords
        keywords = soup.find_all('meta', attrs={"name": "keywords"})
        if len(keywords) > 1:
            issues["duplicate_meta"].append({"tag": "meta keywords", "url": url})
        elif keywords:
            keyword_content = keywords[0].get('content', '')
            if len(keyword_content) > 200:
                issues["meta_length_issues"].append({
                    "tag": "meta keywords",
                    "content": keyword_content,
                    "length": len(keyword_content),
                    "url": url
                })
        
        return issues

    async def _analyze_duplicate_content(self, pages: List[Dict[str, Any]], audit_results: Dict[str, Any]):
        """Analyze pages for duplicate content."""
        titles = defaultdict(list)
        descriptions = defaultdict(list)
        contents = defaultdict(list)
        
        for page in pages:
            url = page.get('url')
            content = page.get('content')
            if not url or not content:
                continue
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # Check titles
            title = soup.find('head').find('title') if soup.find('head') else None
            if not title:
                title = soup.find('title')  # Fallback to searching whole document
            if title and title.string:
                titles[title.string.strip()].append(url)
            
            # Check meta descriptions
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                descriptions[meta_desc['content'].strip()].append(url)
            
            # Check main content (simplified)
            main_content = ' '.join(soup.stripped_strings)
            content_hash = hash(main_content)
            contents[content_hash].append(url)
        
        # Add duplicate content issues
        for title, urls in titles.items():
            if len(urls) > 1:
                for url in urls:
                    audit_results["duplicate_content"].append({
                        "page_url": url,
                        "issue_type": "duplicate_title",
                        "duplicate_with": urls[0] if urls[0] != url else urls[1]
                    })
        
        for desc, urls in descriptions.items():
            if len(urls) > 1:
                for url in urls:
                    audit_results["duplicate_content"].append({
                        "page_url": url,
                        "issue_type": "duplicate_description",
                        "duplicate_with": urls[0] if urls[0] != url else urls[1]
                    })
        
        for content_hash, urls in contents.items():
            if len(urls) > 1:
                for url in urls:
                    audit_results["duplicate_content"].append({
                        "page_url": url,
                        "issue_type": "duplicate_content",
                        "duplicate_with": urls[0] if urls[0] != url else urls[1]
                    })

    def _generate_report(self, audit_results: Dict[str, Any]) -> Dict[str, Any]:
        """Format the audit results into a detailed report."""
        # Calculate total meta issues
        total_meta_issues = sum(
            len(issue.get("missing_meta", [])) +
            len(issue.get("duplicate_meta", [])) +
            len(issue.get("meta_length_issues", []))
            for issue in audit_results["meta_tag_issues"]
        )
        
        report = {
            "summary": {
                "total_pages": audit_results["crawl_stats"]["total_pages"],
                "total_issues": len(audit_results["broken_links"]) + 
                              len(audit_results["duplicate_content"]) + 
                              total_meta_issues,
                "timestamp": audit_results["timestamp"]
            },
            "issues": {
                "broken_links": audit_results["broken_links"],
                "duplicate_content": audit_results["duplicate_content"],
                "meta_tag_issues": audit_results["meta_tag_issues"]
            },
            "technical": {
                "ssl": audit_results["ssl_issues"],
                "sitemap": audit_results["sitemap_present"],
                "robots_txt": audit_results["robots_txt_present"],
                "mobile_friendly": audit_results["mobile_friendly"]
            },
            "performance": audit_results["page_speed_issues"],
            "crawl_stats": {
                "total_pages": audit_results["crawl_stats"]["total_pages"],
                "total_links": len(self._checked_urls),  # Use actual number of unique links checked
                "crawl_time": audit_results["crawl_stats"]["crawl_time"]
            }
        }
        
        return report
