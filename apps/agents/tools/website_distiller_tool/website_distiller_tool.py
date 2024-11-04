import logging
from typing import Type
from pydantic import BaseModel, Field
from crewai_tools.tools.base_tool import BaseTool
from apps.agents.tools.crawl_website_tool.crawl_website_tool import CrawlWebsiteTool
from apps.agents.tools.compression_tool.compression_tool import CompressionTool
import json

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
            # Step 1: Crawl the website
            logger.info(f"Starting website crawl for: {website_url}")
            crawl_tool = CrawlWebsiteTool()
            crawled_content = crawl_tool._run(website_url=website_url)
            
            if not crawled_content:
                return json.dumps({
                    "error": "Crawling failed",
                    "message": "No content was retrieved from the website"
                })

            # Step 2: Process the crawled content
            logger.info("Processing crawled content")
            compression_tool = CompressionTool()
            processed_result = compression_tool._run(
                content=crawled_content,
                max_tokens=max_tokens,
                detail_level=detail_level
            )

            # Parse the compression tool result and add crawling metadata
            result = json.loads(processed_result)
            result["source_url"] = website_url
            
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error in WebsiteDistillerTool: {str(e)}")
            return json.dumps({
                "error": "Processing failed",
                "message": str(e)
            })
