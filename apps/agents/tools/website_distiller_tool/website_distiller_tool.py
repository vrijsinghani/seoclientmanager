import logging
from typing import Type
from pydantic import BaseModel, Field
from crewai_tools.tools.base_tool import BaseTool
from apps.agents.tools.async_crawl_website_tool.async_crawl_website_tool import AsyncCrawlWebsiteTool
from apps.agents.tools.compression_tool.compression_tool import CompressionTool
import json
import asyncio
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

class WebsiteDistillerToolSchema(BaseModel):
    """Input schema for WebsiteDistillerTool."""
    website_url: str = Field(..., description="The website URL to crawl and process")
    max_tokens: int = Field(default=16384, description="Maximum number of tokens in the processed output")
    detail_level: str = Field(
        default="comprehensive",
        description="Detail level: 'comprehensive' (preserve all details), 'detailed' (preserve most details), or 'focused' (key details only)"
    )

    model_config = {
        "extra": "forbid"
    }

class WebsiteDistillerTool(BaseTool):
    name: str = "Website Content Distillation Tool"
    description: str = """
    Crawls a website to extract its content, then processes and organizes the content while preserving important information.
    Combines website crawling with advanced NLP processing for comprehensive content analysis.
    """
    args_schema: Type[BaseModel] = WebsiteDistillerToolSchema

    def _run(
        self,
        website_url: str,
        max_tokens: int = 16384,
        detail_level: str = "comprehensive"
    ) -> str:
        try:
            # Step 1: Normalize the URL
            parsed = urlparse(website_url)
            normalized_url = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path.rstrip('/'),  # Remove trailing slashes
                '',
                parsed.query,
                ''
            ))
            
            # Step 2: Crawl the website
            logger.info(f"Starting website crawl for: {normalized_url}")
            crawl_tool = AsyncCrawlWebsiteTool()
            
            # Create event loop for async crawl
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                crawl_result = loop.run_until_complete(crawl_tool._run(website_url=normalized_url))
            finally:
                loop.close()
            
            if not crawl_result or not isinstance(crawl_result, dict):
                return json.dumps({
                    "error": "Crawling failed",
                    "message": "No content was retrieved from the website"
                })

            # Extract content from crawl result
            content = crawl_result.get('content', [])
            if isinstance(content, list):
                content = '\n'.join(content)
            
            if not content:
                return json.dumps({
                    "error": "Content extraction failed",
                    "message": "No content was found in the crawl result"
                })

            # Add metadata about crawl
            metadata = {
                'total_links': crawl_result.get('total_links', 0),
                'links_visited': len(crawl_result.get('links_visited', [])),
                'source_url': website_url
            }

            # Step 2: Process the crawled content
            logger.info("Processing crawled content")
            compression_tool = CompressionTool()
            processed_result = compression_tool._run(
                content=content,
                max_tokens=max_tokens,
                detail_level=detail_level
            )

            # Parse the compression tool result and add crawling metadata
            compression_data = json.loads(processed_result)
            
            # Format the result for client profile tool
            result = {
                'processed_content': compression_data.get('processed_content', ''),
                'total_links': crawl_result.get('total_links', 0),
                'links_visited': len(crawl_result.get('links_visited', [])),
                'source_url': website_url,
            }
            
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error in WebsiteDistillerTool: {str(e)}")
            return json.dumps({
                "error": "Processing failed",
                "message": str(e)
            })
