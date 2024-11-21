from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from typing import Optional
import logging
from playwright.sync_api import sync_playwright
import os
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class ScreenshotToolSchema(BaseModel):
    """Schema for ScreenshotTool parameters"""
    url: str = Field(
        description="The URL of the webpage to screenshot",
    )
    wait_time: Optional[int] = Field(
        description="Time to wait in seconds before taking screenshot",
        default=5
    )
    full_page: Optional[bool] = Field(
        description="Whether to capture full page or viewport",
        default=True
    )
    output_path: Optional[str] = Field(
        description="Path to save the screenshot",
        default=None
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://example.com",
                    "wait_time": 5,
                    "full_page": True,
                    "output_path": "/path/to/screenshot.png"
                }
            ]
        }
    }

class ScreenshotTool(BaseTool):
    name: str = "Screenshot Tool"
    description: str = "Take screenshots of webpages"
    args_schema: type[ScreenshotToolSchema] = ScreenshotToolSchema

    def _run(self, url: str, wait_time: int = 5, 
             full_page: bool = True, output_path: Optional[str] = None) -> str:
        """Take a screenshot of the specified webpage"""
        try:
            # Generate default output path if none provided
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
                output_path = os.path.join("media", "screenshots", filename)

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                time.sleep(wait_time)  # Wait for content to load
                page.screenshot(path=output_path, full_page=full_page)
                browser.close()

            return f"Screenshot saved to {output_path}"
        except Exception as e:
            logger.error(f"Screenshot error: {str(e)}")
            return f"Error taking screenshot: {str(e)}"

    async def _arun(self, url: str, wait_time: int = 5,
                    full_page: bool = True, output_path: Optional[str] = None) -> str:
        """Async version of screenshot tool"""
        return self._run(url, wait_time, full_page, output_path)

# Initialize the tool instance
screenshot_tool = ScreenshotTool()