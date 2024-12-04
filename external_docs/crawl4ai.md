# Browser Configuration

Crawl4AI supports multiple browser engines and offers extensive configuration options for browser behavior.

## Browser Types

Choose from three browser engines:

```python
# Chromium (default)
async with AsyncWebCrawler(browser_type="chromium") as crawler:
    result = await crawler.arun(url="https://example.com")

# Firefox
async with AsyncWebCrawler(browser_type="firefox") as crawler:
    result = await crawler.arun(url="https://example.com")

# WebKit
async with AsyncWebCrawler(browser_type="webkit") as crawler:
    result = await crawler.arun(url="https://example.com")
```

## Basic Configuration

Common browser settings:

```python
async with AsyncWebCrawler(
    headless=True,           # Run in headless mode (no GUI)
    verbose=True,           # Enable detailed logging
    sleep_on_close=False    # No delay when closing browser
) as crawler:
    result = await crawler.arun(url="https://example.com")
```

## Identity Management

Control how your crawler appears to websites:

```python
# Custom user agent
async with AsyncWebCrawler(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
) as crawler:
    result = await crawler.arun(url="https://example.com")

# Custom headers
headers = {
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache"
}
async with AsyncWebCrawler(headers=headers) as crawler:
    result = await crawler.arun(url="https://example.com")
```

## Screenshot Capabilities

Capture page screenshots with enhanced error handling:

```python
result = await crawler.arun(
    url="https://example.com",
    screenshot=True,                # Enable screenshot
    screenshot_wait_for=2.0        # Wait 2 seconds before capture
)

if result.screenshot:  # Base64 encoded image
    import base64
    with open("screenshot.png", "wb") as f:
        f.write(base64.b64decode(result.screenshot))
```

## Timeouts and Waiting

Control page loading behavior:

```python
result = await crawler.arun(
    url="https://example.com",
    page_timeout=60000,              # Page load timeout (ms)
    delay_before_return_html=2.0,    # Wait before content capture
    wait_for="css:.dynamic-content"  # Wait for specific element
)
```

## JavaScript Execution

Execute custom JavaScript before crawling:

```python
# Single JavaScript command
result = await crawler.arun(
    url="https://example.com",
    js_code="window.scrollTo(0, document.body.scrollHeight);"
)

# Multiple commands
js_commands = [
    "window.scrollTo(0, document.body.scrollHeight);",
    "document.querySelector('.load-more').click();"
]
result = await crawler.arun(
    url="https://example.com",
    js_code=js_commands
)
```

## Proxy Configuration

Use proxies for enhanced access:

```python
# Simple proxy
async with AsyncWebCrawler(
    proxy="http://proxy.example.com:8080"
) as crawler:
    result = await crawler.arun(url="https://example.com")

# Proxy with authentication
proxy_config = {
    "server": "http://proxy.example.com:8080",
    "username": "user",
    "password": "pass"
}
async with AsyncWebCrawler(proxy_config=proxy_config) as crawler:
    result = await crawler.arun(url="https://example.com")
```

## Anti-Detection Features

Enable stealth features to avoid bot detection:

```python
result = await crawler.arun(
    url="https://example.com",
    simulate_user=True,        # Simulate human behavior
    override_navigator=True,   # Mask automation signals
    magic=True               # Enable all anti-detection features
)
```

## Handling Dynamic Content

Configure browser to handle dynamic content:

```python
# Wait for dynamic content
result = await crawler.arun(
    url="https://example.com",
    wait_for="js:() => document.querySelector('.content').children.length > 10",
    process_iframes=True     # Process iframe content
)

# Handle lazy-loaded images
result = await crawler.arun(
    url="https://example.com",
    js_code="window.scrollTo(0, document.body.scrollHeight);",
    delay_before_return_html=2.0  # Wait for images to load
)
```

## Comprehensive Example

Here's how to combine various browser configurations:

```python
async def crawl_with_advanced_config(url: str):
    async with AsyncWebCrawler(
        # Browser setup
        browser_type="chromium",
        headless=True,
        verbose=True,
        
        # Identity
        user_agent="Custom User Agent",
        headers={"Accept-Language": "en-US"},
        
        # Proxy setup
        proxy="http://proxy.example.com:8080"
    ) as crawler:
        result = await crawler.arun(
            url=url,
            # Content handling
            process_iframes=True,
            screenshot=True,
            
            # Timing
            page_timeout=60000,
            delay_before_return_html=2.0,
            
            # Anti-detection
            magic=True,
            simulate_user=True,
            
            # Dynamic content
            js_code=[
                "window.scrollTo(0, document.body.scrollHeight);",
                "document.querySelector('.load-more')?.click();"
            ],
            wait_for="css:.dynamic-content"
        )
        
        return {
            "content": result.markdown,
            "screenshot": result.screenshot,
            "success": result.success
        }
```# Content Selection

Crawl4AI provides multiple ways to select and filter specific content from webpages. Learn how to precisely target the content you need.

## CSS Selectors

The simplest way to extract specific content:

```python
# Extract specific content using CSS selector
result = await crawler.arun(
    url="https://example.com",
    css_selector=".main-article"  # Target main article content
)

# Multiple selectors
result = await crawler.arun(
    url="https://example.com",
    css_selector="article h1, article .content"  # Target heading and content
)
```

## Content Filtering

Control what content is included or excluded:

```python
result = await crawler.arun(
    url="https://example.com",
    # Content thresholds
    word_count_threshold=10,        # Minimum words per block
    
    # Tag exclusions
    excluded_tags=['form', 'header', 'footer', 'nav'],
    
    # Link filtering
    exclude_external_links=True,    # Remove external links
    exclude_social_media_links=True,  # Remove social media links
    
    # Media filtering
    exclude_external_images=True   # Remove external images
)
```

## Iframe Content

Process content inside iframes:

```python
result = await crawler.arun(
    url="https://example.com",
    process_iframes=True,  # Extract iframe content
    remove_overlay_elements=True  # Remove popups/modals that might block iframes
)
```

## Structured Content Selection

### Using LLMs for Smart Selection

Use LLMs to intelligently extract specific types of content:

```python
from pydantic import BaseModel
from crawl4ai.extraction_strategy import LLMExtractionStrategy

class ArticleContent(BaseModel):
    title: str
    main_points: List[str]
    conclusion: str

strategy = LLMExtractionStrategy(
    provider="ollama/nemotron",  # Works with any supported LLM
    schema=ArticleContent.schema(),
    instruction="Extract the main article title, key points, and conclusion"
)

result = await crawler.arun(
    url="https://example.com",
    extraction_strategy=strategy
)
article = json.loads(result.extracted_content)
```

### Pattern-Based Selection

For repeated content patterns (like product listings, news feeds):

```python
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

schema = {
    "name": "News Articles",
    "baseSelector": "article.news-item",  # Repeated element
    "fields": [
        {"name": "headline", "selector": "h2", "type": "text"},
        {"name": "summary", "selector": ".summary", "type": "text"},
        {"name": "category", "selector": ".category", "type": "text"},
        {
            "name": "metadata",
            "type": "nested",
            "fields": [
                {"name": "author", "selector": ".author", "type": "text"},
                {"name": "date", "selector": ".date", "type": "text"}
            ]
        }
    ]
}

strategy = JsonCssExtractionStrategy(schema)
result = await crawler.arun(
    url="https://example.com",
    extraction_strategy=strategy
)
articles = json.loads(result.extracted_content)
```

## Domain-Based Filtering

Control content based on domains:

```python
result = await crawler.arun(
    url="https://example.com",
    exclude_domains=["ads.com", "tracker.com"],
    exclude_social_media_domains=["facebook.com", "twitter.com"],  # Custom social media domains to exclude
    exclude_social_media_links=True
)
```

## Media Selection

Select specific types of media:

```python
result = await crawler.arun(url="https://example.com")

# Access different media types
images = result.media["images"]  # List of image details
videos = result.media["videos"]  # List of video details
audios = result.media["audios"]  # List of audio details

# Image with metadata
for image in images:
    print(f"URL: {image['src']}")
    print(f"Alt text: {image['alt']}")
    print(f"Description: {image['desc']}")
    print(f"Relevance score: {image['score']}")
```

## Comprehensive Example

Here's how to combine different selection methods:

```python
async def extract_article_content(url: str):
    # Define structured extraction
    article_schema = {
        "name": "Article",
        "baseSelector": "article.main",
        "fields": [
            {"name": "title", "selector": "h1", "type": "text"},
            {"name": "content", "selector": ".content", "type": "text"}
        ]
    }
    
    # Define LLM extraction
    class ArticleAnalysis(BaseModel):
        key_points: List[str]
        sentiment: str
        category: str

    async with AsyncWebCrawler() as crawler:
        # Get structured content
        pattern_result = await crawler.arun(
            url=url,
            extraction_strategy=JsonCssExtractionStrategy(article_schema),
            word_count_threshold=10,
            excluded_tags=['nav', 'footer'],
            exclude_external_links=True
        )
        
        # Get semantic analysis
        analysis_result = await crawler.arun(
            url=url,
            extraction_strategy=LLMExtractionStrategy(
                provider="ollama/nemotron",
                schema=ArticleAnalysis.schema(),
                instruction="Analyze the article content"
            )
        )
        
        # Combine results
        return {
            "article": json.loads(pattern_result.extracted_content),
            "analysis": json.loads(analysis_result.extracted_content),
            "media": pattern_result.media
        }
```# Installation 💻

Crawl4AI offers flexible installation options to suit various use cases. You can install it as a Python package, use it with Docker, or run it as a local server.

## Option 1: Python Package Installation (Recommended)

Crawl4AI is now available on PyPI, making installation easier than ever. Choose the option that best fits your needs:

### Basic Installation

For basic web crawling and scraping tasks:

```bash
pip install crawl4ai
playwright install # Install Playwright dependencies
```

### Installation with PyTorch

For advanced text clustering (includes CosineSimilarity cluster strategy):

```bash
pip install crawl4ai[torch]
```

### Installation with Transformers

For text summarization and Hugging Face models:

```bash
pip install crawl4ai[transformer]
```

### Full Installation

For all features:

```bash
pip install crawl4ai[all]
```

### Development Installation

For contributors who plan to modify the source code:

```bash
git clone https://github.com/unclecode/crawl4ai.git
cd crawl4ai
pip install -e ".[all]"
playwright install # Install Playwright dependencies
```

💡 After installation with "torch", "transformer", or "all" options, it's recommended to run the following CLI command to load the required models:

```bash
crawl4ai-download-models
```

This is optional but will boost the performance and speed of the crawler. You only need to do this once after installation.

## Option 2: Using Docker (Coming Soon)

Docker support for Crawl4AI is currently in progress and will be available soon. This will allow you to run Crawl4AI in a containerized environment, ensuring consistency across different systems.

## Option 3: Local Server Installation

For those who prefer to run Crawl4AI as a local server, instructions will be provided once the Docker implementation is complete.

## Verifying Your Installation

After installation, you can verify that Crawl4AI is working correctly by running a simple Python script:

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(url="https://www.example.com")
        print(result.markdown[:500])  # Print first 500 characters

if __name__ == "__main__":
    asyncio.run(main())
```

This script should successfully crawl the example website and print the first 500 characters of the extracted content.

## Getting Help

If you encounter any issues during installation or usage, please check the [documentation](https://crawl4ai.com/mkdocs/) or raise an issue on the [GitHub repository](https://github.com/unclecode/crawl4ai/issues).

Happy crawling! 🕷️🤖# Output Formats

Crawl4AI provides multiple output formats to suit different needs, from raw HTML to structured data using LLM or pattern-based extraction.

## Basic Formats

```python
result = await crawler.arun(url="https://example.com")

# Access different formats
raw_html = result.html           # Original HTML
clean_html = result.cleaned_html # Sanitized HTML
markdown = result.markdown       # Standard markdown
fit_md = result.fit_markdown    # Most relevant content in markdown
```

## Raw HTML

Original, unmodified HTML from the webpage. Useful when you need to:
- Preserve the exact page structure
- Process HTML with your own tools
- Debug page issues

```python
result = await crawler.arun(url="https://example.com")
print(result.html)  # Complete HTML including headers, scripts, etc.
```

## Cleaned HTML

Sanitized HTML with unnecessary elements removed. Automatically:
- Removes scripts and styles
- Cleans up formatting
- Preserves semantic structure

```python
result = await crawler.arun(
    url="https://example.com",
    excluded_tags=['form', 'header', 'footer'],  # Additional tags to remove
    keep_data_attributes=False  # Remove data-* attributes
)
print(result.cleaned_html)
```

## Standard Markdown

HTML converted to clean markdown format. Great for:
- Content analysis
- Documentation
- Readability

```python
result = await crawler.arun(
    url="https://example.com",
    include_links_on_markdown=True  # Include links in markdown
)
print(result.markdown)
```

## Fit Markdown

Most relevant content extracted and converted to markdown. Ideal for:
- Article extraction
- Main content focus
- Removing boilerplate

```python
result = await crawler.arun(url="https://example.com")
print(result.fit_markdown)  # Only the main content
```

## Structured Data Extraction

Crawl4AI offers two powerful approaches for structured data extraction:

### 1. LLM-Based Extraction

Use any LLM (OpenAI, HuggingFace, Ollama, etc.) to extract structured data with high accuracy:

```python
from pydantic import BaseModel
from crawl4ai.extraction_strategy import LLMExtractionStrategy

class KnowledgeGraph(BaseModel):
    entities: List[dict]
    relationships: List[dict]

strategy = LLMExtractionStrategy(
    provider="ollama/nemotron",  # or "huggingface/...", "ollama/..."
    api_token="your-token",   # not needed for Ollama
    schema=KnowledgeGraph.schema(),
    instruction="Extract entities and relationships from the content"
)

result = await crawler.arun(
    url="https://example.com",
    extraction_strategy=strategy
)
knowledge_graph = json.loads(result.extracted_content)
```

### 2. Pattern-Based Extraction

For pages with repetitive patterns (e.g., product listings, article feeds), use JsonCssExtractionStrategy:

```python
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

schema = {
    "name": "Product Listing",
    "baseSelector": ".product-card",  # Repeated element
    "fields": [
        {"name": "title", "selector": "h2", "type": "text"},
        {"name": "price", "selector": ".price", "type": "text"},
        {"name": "description", "selector": ".desc", "type": "text"}
    ]
}

strategy = JsonCssExtractionStrategy(schema)
result = await crawler.arun(
    url="https://example.com",
    extraction_strategy=strategy
)
products = json.loads(result.extracted_content)
```

## Content Customization

### HTML to Text Options

Configure markdown conversion:

```python
result = await crawler.arun(
    url="https://example.com",
    html2text={
        "escape_dot": False,
        "body_width": 0,
        "protect_links": True,
        "unicode_snob": True
    }
)
```

### Content Filters

Control what content is included:

```python
result = await crawler.arun(
    url="https://example.com",
    word_count_threshold=10,        # Minimum words per block
    exclude_external_links=True,    # Remove external links
    exclude_external_images=True,   # Remove external images
    excluded_tags=['form', 'nav']   # Remove specific HTML tags
)
```

## Comprehensive Example

Here's how to use multiple output formats together:

```python
async def crawl_content(url: str):
    async with AsyncWebCrawler() as crawler:
        # Extract main content with fit markdown
        result = await crawler.arun(
            url=url,
            word_count_threshold=10,
            exclude_external_links=True
        )
        
        # Get structured data using LLM
        llm_result = await crawler.arun(
            url=url,
            extraction_strategy=LLMExtractionStrategy(
                provider="ollama/nemotron",
                schema=YourSchema.schema(),
                instruction="Extract key information"
            )
        )
        
        # Get repeated patterns (if any)
        pattern_result = await crawler.arun(
            url=url,
            extraction_strategy=JsonCssExtractionStrategy(your_schema)
        )
        
        return {
            "main_content": result.fit_markdown,
            "structured_data": json.loads(llm_result.extracted_content),
            "pattern_data": json.loads(pattern_result.extracted_content),
            "media": result.media
        }
```# Page Interaction

Crawl4AI provides powerful features for interacting with dynamic webpages, handling JavaScript execution, and managing page events.

## JavaScript Execution

### Basic Execution

```python
# Single JavaScript command
result = await crawler.arun(
    url="https://example.com",
    js_code="window.scrollTo(0, document.body.scrollHeight);"
)

# Multiple commands
js_commands = [
    "window.scrollTo(0, document.body.scrollHeight);",
    "document.querySelector('.load-more').click();",
    "document.querySelector('#consent-button').click();"
]
result = await crawler.arun(
    url="https://example.com",
    js_code=js_commands
)
```

## Wait Conditions

### CSS-Based Waiting

Wait for elements to appear:

```python
result = await crawler.arun(
    url="https://example.com",
    wait_for="css:.dynamic-content"  # Wait for element with class 'dynamic-content'
)
```

### JavaScript-Based Waiting

Wait for custom conditions:

```python
# Wait for number of elements
wait_condition = """() => {
    return document.querySelectorAll('.item').length > 10;
}"""

result = await crawler.arun(
    url="https://example.com",
    wait_for=f"js:{wait_condition}"
)

# Wait for dynamic content to load
wait_for_content = """() => {
    const content = document.querySelector('.content');
    return content && content.innerText.length > 100;
}"""

result = await crawler.arun(
    url="https://example.com",
    wait_for=f"js:{wait_for_content}"
)
```

## Handling Dynamic Content

### Load More Content

Handle infinite scroll or load more buttons:

```python
# Scroll and wait pattern
result = await crawler.arun(
    url="https://example.com",
    js_code=[
        # Scroll to bottom
        "window.scrollTo(0, document.body.scrollHeight);",
        # Click load more if exists
        "const loadMore = document.querySelector('.load-more'); if(loadMore) loadMore.click();"
    ],
    # Wait for new content
    wait_for="js:() => document.querySelectorAll('.item').length > previousCount"
)
```

### Form Interaction

Handle forms and inputs:

```python
js_form_interaction = """
    // Fill form fields
    document.querySelector('#search').value = 'search term';
    // Submit form
    document.querySelector('form').submit();
"""

result = await crawler.arun(
    url="https://example.com",
    js_code=js_form_interaction,
    wait_for="css:.results"  # Wait for results to load
)
```

## Timing Control

### Delays and Timeouts

Control timing of interactions:

```python
result = await crawler.arun(
    url="https://example.com",
    page_timeout=60000,              # Page load timeout (ms)
    delay_before_return_html=2.0,    # Wait before capturing content
)
```

## Complex Interactions Example

Here's an example of handling a dynamic page with multiple interactions:

```python
async def crawl_dynamic_content():
    async with AsyncWebCrawler() as crawler:
        # Initial page load
        result = await crawler.arun(
            url="https://example.com",
            # Handle cookie consent
            js_code="document.querySelector('.cookie-accept')?.click();",
            wait_for="css:.main-content"
        )

        # Load more content
        session_id = "dynamic_session"  # Keep session for multiple interactions
        
        for page in range(3):  # Load 3 pages of content
            result = await crawler.arun(
                url="https://example.com",
                session_id=session_id,
                js_code=[
                    # Scroll to bottom
                    "window.scrollTo(0, document.body.scrollHeight);",
                    # Store current item count
                    "window.previousCount = document.querySelectorAll('.item').length;",
                    # Click load more
                    "document.querySelector('.load-more')?.click();"
                ],
                # Wait for new items
                wait_for="""() => {
                    const currentCount = document.querySelectorAll('.item').length;
                    return currentCount > window.previousCount;
                }""",
                # Only execute JS without reloading page
                js_only=True if page > 0 else False
            )
            
            # Process content after each load
            print(f"Page {page + 1} items:", len(result.cleaned_html))
            
        # Clean up session
        await crawler.crawler_strategy.kill_session(session_id)
```

## Using with Extraction Strategies

Combine page interaction with structured extraction:

```python
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, LLMExtractionStrategy

# Pattern-based extraction after interaction
schema = {
    "name": "Dynamic Items",
    "baseSelector": ".item",
    "fields": [
        {"name": "title", "selector": "h2", "type": "text"},
        {"name": "description", "selector": ".desc", "type": "text"}
    ]
}

result = await crawler.arun(
    url="https://example.com",
    js_code="window.scrollTo(0, document.body.scrollHeight);",
    wait_for="css:.item:nth-child(10)",  # Wait for 10 items
    extraction_strategy=JsonCssExtractionStrategy(schema)
)

# Or use LLM to analyze dynamic content
class ContentAnalysis(BaseModel):
    topics: List[str]
    summary: str

result = await crawler.arun(
    url="https://example.com",
    js_code="document.querySelector('.show-more').click();",
    wait_for="css:.full-content",
    extraction_strategy=LLMExtractionStrategy(
        provider="ollama/nemotron",
        schema=ContentAnalysis.schema(),
        instruction="Analyze the full content"
    )
)
```# Quick Start Guide 🚀

Welcome to the Crawl4AI Quickstart Guide! In this tutorial, we'll walk you through the basic usage of Crawl4AI with a friendly and humorous tone. We'll cover everything from basic usage to advanced features like chunking and extraction strategies, all with the power of asynchronous programming. Let's dive in! 🌟

## Getting Started 🛠️

First, let's import the necessary modules and create an instance of `AsyncWebCrawler`. We'll use an async context manager, which handles the setup and teardown of the crawler for us.

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler(verbose=True) as crawler:
        # We'll add our crawling code here
        pass

if __name__ == "__main__":
    asyncio.run(main())
```

### Basic Usage

Simply provide a URL and let Crawl4AI do the magic!

```python
async def main():
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(url="https://www.nbcnews.com/business")
        print(f"Basic crawl result: {result.markdown[:500]}")  # Print first 500 characters

asyncio.run(main())
```

### Taking Screenshots 📸

Capture screenshots of web pages easily:

```python
async def capture_and_save_screenshot(url: str, output_path: str):
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=url,
            screenshot=True,
            bypass_cache=True
        )
        
        if result.success and result.screenshot:
            import base64
            screenshot_data = base64.b64decode(result.screenshot)
            with open(output_path, 'wb') as f:
                f.write(screenshot_data)
            print(f"Screenshot saved successfully to {output_path}")
        else:
            print("Failed to capture screenshot")
```

### Browser Selection 🌐

Crawl4AI supports multiple browser engines. Here's how to use different browsers:

```python
# Use Firefox
async with AsyncWebCrawler(browser_type="firefox", verbose=True, headless=True) as crawler:
    result = await crawler.arun(url="https://www.example.com", bypass_cache=True)

# Use WebKit
async with AsyncWebCrawler(browser_type="webkit", verbose=True, headless=True) as crawler:
    result = await crawler.arun(url="https://www.example.com", bypass_cache=True)

# Use Chromium (default)
async with AsyncWebCrawler(verbose=True, headless=True) as crawler:
    result = await crawler.arun(url="https://www.example.com", bypass_cache=True)
```

### User Simulation 🎭

Simulate real user behavior to avoid detection:

```python
async with AsyncWebCrawler(verbose=True, headless=True) as crawler:
    result = await crawler.arun(
        url="YOUR-URL-HERE",
        bypass_cache=True,
        simulate_user=True,  # Causes random mouse movements and clicks
        override_navigator=True  # Makes the browser appear more like a real user
    )
```

### Understanding Parameters 🧠

By default, Crawl4AI caches the results of your crawls. This means that subsequent crawls of the same URL will be much faster! Let's see this in action.

```python
async def main():
    async with AsyncWebCrawler(verbose=True) as crawler:
        # First crawl (caches the result)
        result1 = await crawler.arun(url="https://www.nbcnews.com/business")
        print(f"First crawl result: {result1.markdown[:100]}...")

        # Force to crawl again
        result2 = await crawler.arun(url="https://www.nbcnews.com/business", bypass_cache=True)
        print(f"Second crawl result: {result2.markdown[:100]}...")

asyncio.run(main())
```

### Adding a Chunking Strategy 🧩

Let's add a chunking strategy: `RegexChunking`! This strategy splits the text based on a given regex pattern.

```python
from crawl4ai.chunking_strategy import RegexChunking

async def main():
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://www.nbcnews.com/business",
            chunking_strategy=RegexChunking(patterns=["\n\n"])
        )
        print(f"RegexChunking result: {result.extracted_content[:200]}...")

asyncio.run(main())
```

### Using LLMExtractionStrategy with Different Providers 🤖

Crawl4AI supports multiple LLM providers for extraction:

```python
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel, Field

class OpenAIModelFee(BaseModel):
    model_name: str = Field(..., description="Name of the OpenAI model.")
    input_fee: str = Field(..., description="Fee for input token for the OpenAI model.")
    output_fee: str = Field(..., description="Fee for output token for the OpenAI model.")

# OpenAI
await extract_structured_data_using_llm("openai/gpt-4o", os.getenv("OPENAI_API_KEY"))

# Hugging Face
await extract_structured_data_using_llm(
    "huggingface/meta-llama/Meta-Llama-3.1-8B-Instruct", 
    os.getenv("HUGGINGFACE_API_KEY")
)

# Ollama
await extract_structured_data_using_llm("ollama/llama3.2")

# With custom headers
custom_headers = {
    "Authorization": "Bearer your-custom-token",
    "X-Custom-Header": "Some-Value"
}
await extract_structured_data_using_llm(extra_headers=custom_headers)
```

### Knowledge Graph Generation 🕸️

Generate knowledge graphs from web content:

```python
from pydantic import BaseModel
from typing import List

class Entity(BaseModel):
    name: str
    description: str
    
class Relationship(BaseModel):
    entity1: Entity
    entity2: Entity
    description: str
    relation_type: str

class KnowledgeGraph(BaseModel):
    entities: List[Entity]
    relationships: List[Relationship]

extraction_strategy = LLMExtractionStrategy(
    provider='openai/gpt-4o-mini',
    api_token=os.getenv('OPENAI_API_KEY'),
    schema=KnowledgeGraph.model_json_schema(),
    extraction_type="schema",
    instruction="Extract entities and relationships from the given text."
)

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url="https://paulgraham.com/love.html",
        bypass_cache=True,
        extraction_strategy=extraction_strategy
    )
```

### Advanced Session-Based Crawling with Dynamic Content 🔄

For modern web applications with dynamic content loading, here's how to handle pagination and content updates:

```python
async def crawl_dynamic_content():
    async with AsyncWebCrawler(verbose=True) as crawler:
        url = "https://github.com/microsoft/TypeScript/commits/main"
        session_id = "typescript_commits_session"
        
        js_next_page = """
        const button = document.querySelector('a[data-testid="pagination-next-button"]');
        if (button) button.click();
        """

        wait_for = """() => {
            const commits = document.querySelectorAll('li.Box-sc-g0xbh4-0 h4');
            if (commits.length === 0) return false;
            const firstCommit = commits[0].textContent.trim();
            return firstCommit !== window.firstCommit;
        }"""
        
        schema = {
            "name": "Commit Extractor",
            "baseSelector": "li.Box-sc-g0xbh4-0",
            "fields": [
                {
                    "name": "title",
                    "selector": "h4.markdown-title",
                    "type": "text",
                    "transform": "strip",
                },
            ],
        }
        extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

        for page in range(3):  # Crawl 3 pages
            result = await crawler.arun(
                url=url,
                session_id=session_id,
                css_selector="li.Box-sc-g0xbh4-0",
                extraction_strategy=extraction_strategy,
                js_code=js_next_page if page > 0 else None,
                wait_for=wait_for if page > 0 else None,
                js_only=page > 0,
                bypass_cache=True,
                headless=False,
            )

        await crawler.crawler_strategy.kill_session(session_id)
```

### Handling Overlays and Fitting Content 📏

Remove overlay elements and fit content appropriately:

```python
async with AsyncWebCrawler(headless=False) as crawler:
    result = await crawler.arun(
        url="your-url-here",
        bypass_cache=True,
        word_count_threshold=10,
        remove_overlay_elements=True,
        screenshot=True
    )
```

## Performance Comparison 🏎️

Crawl4AI offers impressive performance compared to other solutions:

```python
# Firecrawl comparison
from firecrawl import FirecrawlApp
app = FirecrawlApp(api_key=os.environ['FIRECRAWL_API_KEY'])
start = time.time()
scrape_status = app.scrape_url(
    'https://www.nbcnews.com/business',
    params={'formats': ['markdown', 'html']}
)
end = time.time()

# Crawl4AI comparison
async with AsyncWebCrawler() as crawler:
    start = time.time()
    result = await crawler.arun(
        url="https://www.nbcnews.com/business",
        word_count_threshold=0,
        bypass_cache=True,
        verbose=False,
    )
    end = time.time()
```

Note: Performance comparisons should be conducted in environments with stable and fast internet connections for accurate results.

## Congratulations! 🎉

You've made it through the updated Crawl4AI Quickstart Guide! Now you're equipped with even more powerful features to crawl the web asynchronously like a pro! 🕸️

Happy crawling! 🚀# Simple Crawling

This guide covers the basics of web crawling with Crawl4AI. You'll learn how to set up a crawler, make your first request, and understand the response.

## Basic Usage

Here's the simplest way to crawl a webpage:

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url="https://example.com")
        print(result.markdown)  # Print clean markdown content

if __name__ == "__main__":
    asyncio.run(main())
```

## Understanding the Response

The `arun()` method returns a `CrawlResult` object with several useful properties. Here's a quick overview (see [CrawlResult](../api/crawl-result.md) for complete details):

```python
result = await crawler.arun(url="https://example.com")

# Different content formats
print(result.html)         # Raw HTML
print(result.cleaned_html) # Cleaned HTML
print(result.markdown)     # Markdown version
print(result.fit_markdown) # Most relevant content in markdown

# Check success status
print(result.success)      # True if crawl succeeded
print(result.status_code)  # HTTP status code (e.g., 200, 404)

# Access extracted media and links
print(result.media)        # Dictionary of found media (images, videos, audio)
print(result.links)        # Dictionary of internal and external links
```

## Adding Basic Options

Customize your crawl with these common options:

```python
result = await crawler.arun(
    url="https://example.com",
    word_count_threshold=10,        # Minimum words per content block
    exclude_external_links=True,    # Remove external links
    remove_overlay_elements=True,   # Remove popups/modals
    process_iframes=True           # Process iframe content
)
```

## Handling Errors

Always check if the crawl was successful:

```python
result = await crawler.arun(url="https://example.com")
if not result.success:
    print(f"Crawl failed: {result.error_message}")
    print(f"Status code: {result.status_code}")
```

## Logging and Debugging

Enable verbose mode for detailed logging:

```python
async with AsyncWebCrawler(verbose=True) as crawler:
    result = await crawler.arun(url="https://example.com")
```

## Complete Example

Here's a more comprehensive example showing common usage patterns:

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://example.com",
            # Content filtering
            word_count_threshold=10,
            excluded_tags=['form', 'header'],
            exclude_external_links=True,
            
            # Content processing
            process_iframes=True,
            remove_overlay_elements=True,
            
            # Cache control
            bypass_cache=False  # Use cache if available
        )
        
        if result.success:
            # Print clean content
            print("Content:", result.markdown[:500])  # First 500 chars
            
            # Process images
            for image in result.media["images"]:
                print(f"Found image: {image['src']}")
            
            # Process links
            for link in result.links["internal"]:
                print(f"Internal link: {link['href']}")
                
        else:
            print(f"Crawl failed: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
```
# Content Processing

Crawl4AI provides powerful content processing capabilities that help you extract clean, relevant content from web pages. This guide covers content cleaning, media handling, link analysis, and metadata extraction.

## Content Cleaning

### Understanding Clean Content
When crawling web pages, you often encounter a lot of noise - advertisements, navigation menus, footers, popups, and other irrelevant content. Crawl4AI automatically cleans this noise using several approaches:

1. **Basic Cleaning**: Removes unwanted HTML elements and attributes
2. **Content Relevance**: Identifies and preserves meaningful content blocks
3. **Layout Analysis**: Understands page structure to identify main content areas

```python
result = await crawler.arun(
    url="https://example.com",
    word_count_threshold=10,        # Remove blocks with fewer words
    excluded_tags=['form', 'nav'],  # Remove specific HTML tags
    remove_overlay_elements=True    # Remove popups/modals
)

# Get clean content
print(result.cleaned_html)  # Cleaned HTML
print(result.markdown)      # Clean markdown version
```

### Fit Markdown: Smart Content Extraction
One of Crawl4AI's most powerful features is `fit_markdown`. This feature uses advanced heuristics to identify and extract the main content from a webpage while excluding irrelevant elements.

#### How Fit Markdown Works
- Analyzes content density and distribution
- Identifies content patterns and structures
- Removes boilerplate content (headers, footers, sidebars)
- Preserves the most relevant content blocks
- Maintains content hierarchy and formatting

#### Perfect For:
- Blog posts and articles
- News content
- Documentation pages
- Any page with a clear main content area

#### Not Recommended For:
- E-commerce product listings
- Search results pages
- Social media feeds
- Pages with multiple equal-weight content sections

```python
result = await crawler.arun(url="https://example.com")

# Get the most relevant content
main_content = result.fit_markdown

# Compare with regular markdown
all_content = result.markdown

print(f"Fit Markdown Length: {len(main_content)}")
print(f"Regular Markdown Length: {len(all_content)}")
```

#### Example Use Case
```python
async def extract_article_content(url: str) -> str:
    """Extract main article content from a blog or news site."""
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        
        # fit_markdown will focus on the article content,
        # excluding navigation, ads, and other distractions
        return result.fit_markdown
```

## Media Processing

Crawl4AI provides comprehensive media extraction and analysis capabilities. It automatically detects and processes various types of media elements while maintaining their context and relevance.

### Image Processing
The library handles various image scenarios, including:
- Regular images
- Lazy-loaded images
- Background images
- Responsive images
- Image metadata and context

```python
result = await crawler.arun(url="https://example.com")

for image in result.media["images"]:
    # Each image includes rich metadata
    print(f"Source: {image['src']}")
    print(f"Alt text: {image['alt']}")
    print(f"Description: {image['desc']}")
    print(f"Context: {image['context']}")  # Surrounding text
    print(f"Relevance score: {image['score']}")  # 0-10 score
```

### Handling Lazy-Loaded Content
Crawl4aai already handles lazy loading for media elements. You can also customize the wait time for lazy-loaded content:

```python
result = await crawler.arun(
    url="https://example.com",
    wait_for="css:img[data-src]",  # Wait for lazy images
    delay_before_return_html=2.0   # Additional wait time
)
```

### Video and Audio Content
The library extracts video and audio elements with their metadata:

```python
# Process videos
for video in result.media["videos"]:
    print(f"Video source: {video['src']}")
    print(f"Type: {video['type']}")
    print(f"Duration: {video.get('duration')}")
    print(f"Thumbnail: {video.get('poster')}")

# Process audio
for audio in result.media["audios"]:
    print(f"Audio source: {audio['src']}")
    print(f"Type: {audio['type']}")
    print(f"Duration: {audio.get('duration')}")
```

## Link Analysis

Crawl4AI provides sophisticated link analysis capabilities, helping you understand the relationship between pages and identify important navigation patterns.

### Link Classification
The library automatically categorizes links into:
- Internal links (same domain)
- External links (different domains)
- Social media links
- Navigation links
- Content links

```python
result = await crawler.arun(url="https://example.com")

# Analyze internal links
for link in result.links["internal"]:
    print(f"Internal: {link['href']}")
    print(f"Link text: {link['text']}")
    print(f"Context: {link['context']}")  # Surrounding text
    print(f"Type: {link['type']}")  # nav, content, etc.

# Analyze external links
for link in result.links["external"]:
    print(f"External: {link['href']}")
    print(f"Domain: {link['domain']}")
    print(f"Type: {link['type']}")
```

### Smart Link Filtering
Control which links are included in the results:

```python
result = await crawler.arun(
    url="https://example.com",
    exclude_external_links=True,          # Remove external links
    exclude_social_media_links=True,      # Remove social media links
    exclude_social_media_domains=[                # Custom social media domains
        "facebook.com", "twitter.com", "instagram.com"
    ],
    exclude_domains=["ads.example.com"]   # Exclude specific domains
)
```

## Metadata Extraction

Crawl4AI automatically extracts and processes page metadata, providing valuable information about the content:

```python
result = await crawler.arun(url="https://example.com")

metadata = result.metadata
print(f"Title: {metadata['title']}")
print(f"Description: {metadata['description']}")
print(f"Keywords: {metadata['keywords']}")
print(f"Author: {metadata['author']}")
print(f"Published Date: {metadata['published_date']}")
print(f"Modified Date: {metadata['modified_date']}")
print(f"Language: {metadata['language']}")
```

## Best Practices

1. **Use Fit Markdown for Articles**
   ```python
   # Perfect for blog posts, news articles, documentation
   content = result.fit_markdown
   ```

2. **Handle Media Appropriately**
   ```python
   # Filter by relevance score
   relevant_images = [
       img for img in result.media["images"]
       if img['score'] > 5
   ]
   ```

3. **Combine Link Analysis with Content**
   ```python
   # Get content links with context
   content_links = [
       link for link in result.links["internal"]
       if link['type'] == 'content'
   ]
   ```

4. **Clean Content with Purpose**
   ```python
   # Customize cleaning based on your needs
   result = await crawler.arun(
       url=url,
       word_count_threshold=20,      # Adjust based on content type
       keep_data_attributes=False,   # Remove data attributes
       process_iframes=True         # Include iframe content
   )
   ```# Hooks & Auth for AsyncWebCrawler

Crawl4AI's AsyncWebCrawler allows you to customize the behavior of the web crawler using hooks. Hooks are asynchronous functions that are called at specific points in the crawling process, allowing you to modify the crawler's behavior or perform additional actions. This example demonstrates how to use various hooks to customize the asynchronous crawling process.

## Example: Using Crawler Hooks with AsyncWebCrawler

Let's see how we can customize the AsyncWebCrawler using hooks! In this example, we'll:

1. Configure the browser when it's created.
2. Add custom headers before navigating to the URL.
3. Log the current URL after navigation.
4. Perform actions after JavaScript execution.
5. Log the length of the HTML before returning it.

### Hook Definitions

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from playwright.async_api import Page, Browser

async def on_browser_created(browser: Browser):
    print("[HOOK] on_browser_created")
    # Example customization: set browser viewport size
    context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
    page = await context.new_page()
    
    # Example customization: logging in to a hypothetical website
    await page.goto('https://example.com/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'password123')
    await page.click('button[type="submit"]')
    await page.wait_for_selector('#welcome')
    
    # Add a custom cookie
    await context.add_cookies([{'name': 'test_cookie', 'value': 'cookie_value', 'url': 'https://example.com'}])
    
    await page.close()
    await context.close()

async def before_goto(page: Page):
    print("[HOOK] before_goto")
    # Example customization: add custom headers
    await page.set_extra_http_headers({'X-Test-Header': 'test'})

async def after_goto(page: Page):
    print("[HOOK] after_goto")
    # Example customization: log the URL
    print(f"Current URL: {page.url}")

async def on_execution_started(page: Page):
    print("[HOOK] on_execution_started")
    # Example customization: perform actions after JS execution
    await page.evaluate("console.log('Custom JS executed')")

async def before_return_html(page: Page, html: str):
    print("[HOOK] before_return_html")
    # Example customization: log the HTML length
    print(f"HTML length: {len(html)}")
    return page
```

### Using the Hooks with the AsyncWebCrawler

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy

async def main():
    print("\n🔗 Using Crawler Hooks: Let's see how we can customize the AsyncWebCrawler using hooks!")
    
    crawler_strategy = AsyncPlaywrightCrawlerStrategy(verbose=True)
    crawler_strategy.set_hook('on_browser_created', on_browser_created)
    crawler_strategy.set_hook('before_goto', before_goto)
    crawler_strategy.set_hook('after_goto', after_goto)
    crawler_strategy.set_hook('on_execution_started', on_execution_started)
    crawler_strategy.set_hook('before_return_html', before_return_html)
    
    async with AsyncWebCrawler(verbose=True, crawler_strategy=crawler_strategy) as crawler:
        result = await crawler.arun(
            url="https://example.com",
            js_code="window.scrollTo(0, document.body.scrollHeight);",
            wait_for="footer"
        )

    print("📦 Crawler Hooks result:")
    print(result)

asyncio.run(main())
```

### Explanation

- `on_browser_created`: This hook is called when the Playwright browser is created. It sets up the browser context, logs in to a website, and adds a custom cookie.
- `before_goto`: This hook is called right before Playwright navigates to the URL. It adds custom HTTP headers.
- `after_goto`: This hook is called after Playwright navigates to the URL. It logs the current URL.
- `on_execution_started`: This hook is called after any custom JavaScript is executed. It performs additional JavaScript actions.
- `before_return_html`: This hook is called before returning the HTML content. It logs the length of the HTML content.

### Additional Ideas

- **Handling authentication**: Use the `on_browser_created` hook to handle login processes or set authentication tokens.
- **Dynamic header modification**: Modify headers based on the target URL or other conditions in the `before_goto` hook.
- **Content verification**: Use the `after_goto` hook to verify that the expected content is present on the page.
- **Custom JavaScript injection**: Inject and execute custom JavaScript using the `on_execution_started` hook.
- **Content preprocessing**: Modify or analyze the HTML content in the `before_return_html` hook before it's returned.

By using these hooks, you can customize the behavior of the AsyncWebCrawler to suit your specific needs, including handling authentication, modifying requests, and preprocessing content.# Magic Mode & Anti-Bot Protection

Crawl4AI provides powerful anti-detection capabilities, with Magic Mode being the simplest and most comprehensive solution.

## Magic Mode

The easiest way to bypass anti-bot protections:

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url="https://example.com",
        magic=True  # Enables all anti-detection features
    )
```

Magic Mode automatically:
- Masks browser automation signals
- Simulates human-like behavior
- Overrides navigator properties
- Handles cookie consent popups
- Manages browser fingerprinting
- Randomizes timing patterns

## Manual Anti-Bot Options

While Magic Mode is recommended, you can also configure individual anti-detection features:

```python
result = await crawler.arun(
    url="https://example.com",
    simulate_user=True,        # Simulate human behavior
    override_navigator=True    # Mask automation signals
)
```

Note: When `magic=True` is used, you don't need to set these individual options.

## Example: Handling Protected Sites

```python
async def crawl_protected_site(url: str):
    async with AsyncWebCrawler(headless=True) as crawler:
        result = await crawler.arun(
            url=url,
            magic=True,
            remove_overlay_elements=True,  # Remove popups/modals
            page_timeout=60000            # Increased timeout for protection checks
        )
        
        return result.markdown if result.success else None
```
# Proxy & Security

Configure proxy settings and enhance security features in Crawl4AI for reliable data extraction.

## Basic Proxy Setup

Simple proxy configuration:

```python
# Using proxy URL
async with AsyncWebCrawler(
    proxy="http://proxy.example.com:8080"
) as crawler:
    result = await crawler.arun(url="https://example.com")

# Using SOCKS proxy
async with AsyncWebCrawler(
    proxy="socks5://proxy.example.com:1080"
) as crawler:
    result = await crawler.arun(url="https://example.com")
```

## Authenticated Proxy

Use proxy with authentication:

```python
proxy_config = {
    "server": "http://proxy.example.com:8080",
    "username": "user",
    "password": "pass"
}

async with AsyncWebCrawler(proxy_config=proxy_config) as crawler:
    result = await crawler.arun(url="https://example.com")
```

## Rotating Proxies

Example using a proxy rotation service:

```python
async def get_next_proxy():
    # Your proxy rotation logic here
    return {"server": "http://next.proxy.com:8080"}

async with AsyncWebCrawler() as crawler:
    # Update proxy for each request
    for url in urls:
        proxy = await get_next_proxy()
        crawler.update_proxy(proxy)
        result = await crawler.arun(url=url)
```

## Custom Headers

Add security-related headers:

```python
headers = {
    "X-Forwarded-For": "203.0.113.195",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

async with AsyncWebCrawler(headers=headers) as crawler:
    result = await crawler.arun(url="https://example.com")
```

## Combining with Magic Mode

For maximum protection, combine proxy with Magic Mode:

```python
async with AsyncWebCrawler(
    proxy="http://proxy.example.com:8080",
    headers={"Accept-Language": "en-US"}
) as crawler:
    result = await crawler.arun(
        url="https://example.com",
        magic=True  # Enable all anti-detection features
    )
```# Session-Based Crawling for Dynamic Content

In modern web applications, content is often loaded dynamically without changing the URL. Examples include "Load More" buttons, infinite scrolling, or paginated content that updates via JavaScript. To effectively crawl such websites, Crawl4AI provides powerful session-based crawling capabilities.

This guide will explore advanced techniques for crawling dynamic content using Crawl4AI's session management features.

## Understanding Session-Based Crawling

Session-based crawling allows you to maintain a persistent browser session across multiple requests. This is crucial when:

1. The content changes dynamically without URL changes
2. You need to interact with the page (e.g., clicking buttons) between requests
3. The site requires authentication or maintains state across pages

Crawl4AI's `AsyncWebCrawler` class supports session-based crawling through the `session_id` parameter and related methods.

## Basic Concepts

Before diving into examples, let's review some key concepts:

- **Session ID**: A unique identifier for a browsing session. Use the same `session_id` across multiple `arun` calls to maintain state.
- **JavaScript Execution**: Use the `js_code` parameter to execute JavaScript on the page, such as clicking a "Load More" button.
- **CSS Selectors**: Use these to target specific elements for extraction or interaction.
- **Extraction Strategy**: Define how to extract structured data from the page.
- **Wait Conditions**: Specify conditions to wait for before considering the page loaded.

## Example 1: Basic Session-Based Crawling

Let's start with a basic example of session-based crawling:

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def basic_session_crawl():
    async with AsyncWebCrawler(verbose=True) as crawler:
        session_id = "my_session"
        url = "https://example.com/dynamic-content"

        for page in range(3):
            result = await crawler.arun(
                url=url,
                session_id=session_id,
                js_code="document.querySelector('.load-more-button').click();" if page > 0 else None,
                css_selector=".content-item",
                bypass_cache=True
            )
            
            print(f"Page {page + 1}: Found {result.extracted_content.count('.content-item')} items")

        await crawler.crawler_strategy.kill_session(session_id)

asyncio.run(basic_session_crawl())
```

This example demonstrates:
1. Using a consistent `session_id` across multiple `arun` calls
2. Executing JavaScript to load more content after the first page
3. Using a CSS selector to extract specific content
4. Properly closing the session after crawling

## Advanced Technique 1: Custom Execution Hooks

Crawl4AI allows you to set custom hooks that execute at different stages of the crawling process. This is particularly useful for handling complex loading scenarios.

Here's an example that waits for new content to appear before proceeding:

```python
async def advanced_session_crawl_with_hooks():
    first_commit = ""

    async def on_execution_started(page):
        nonlocal first_commit
        try:
            while True:
                await page.wait_for_selector("li.commit-item h4")
                commit = await page.query_selector("li.commit-item h4")
                commit = await commit.evaluate("(element) => element.textContent")
                commit = commit.strip()
                if commit and commit != first_commit:
                    first_commit = commit
                    break
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Warning: New content didn't appear after JavaScript execution: {e}")

    async with AsyncWebCrawler(verbose=True) as crawler:
        crawler.crawler_strategy.set_hook("on_execution_started", on_execution_started)

        url = "https://github.com/example/repo/commits/main"
        session_id = "commit_session"
        all_commits = []

        js_next_page = """
        const button = document.querySelector('a.pagination-next');
        if (button) button.click();
        """

        for page in range(3):
            result = await crawler.arun(
                url=url,
                session_id=session_id,
                css_selector="li.commit-item",
                js_code=js_next_page if page > 0 else None,
                bypass_cache=True,
                js_only=page > 0
            )

            commits = result.extracted_content.select("li.commit-item")
            all_commits.extend(commits)
            print(f"Page {page + 1}: Found {len(commits)} commits")

        await crawler.crawler_strategy.kill_session(session_id)
        print(f"Successfully crawled {len(all_commits)} commits across 3 pages")

asyncio.run(advanced_session_crawl_with_hooks())
```

This technique uses a custom `on_execution_started` hook to ensure new content has loaded before proceeding to the next step.

## Advanced Technique 2: Integrated JavaScript Execution and Waiting

Instead of using separate hooks, you can integrate the waiting logic directly into your JavaScript execution. This approach can be more concise and easier to manage for some scenarios.

Here's an example:

```python
async def integrated_js_and_wait_crawl():
    async with AsyncWebCrawler(verbose=True) as crawler:
        url = "https://github.com/example/repo/commits/main"
        session_id = "integrated_session"
        all_commits = []

        js_next_page_and_wait = """
        (async () => {
            const getCurrentCommit = () => {
                const commits = document.querySelectorAll('li.commit-item h4');
                return commits.length > 0 ? commits[0].textContent.trim() : null;
            };

            const initialCommit = getCurrentCommit();
            const button = document.querySelector('a.pagination-next');
            if (button) button.click();

            while (true) {
                await new Promise(resolve => setTimeout(resolve, 100));
                const newCommit = getCurrentCommit();
                if (newCommit && newCommit !== initialCommit) {
                    break;
                }
            }
        })();
        """

        schema = {
            "name": "Commit Extractor",
            "baseSelector": "li.commit-item",
            "fields": [
                {
                    "name": "title",
                    "selector": "h4.commit-title",
                    "type": "text",
                    "transform": "strip",
                },
            ],
        }
        extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

        for page in range(3):
            result = await crawler.arun(
                url=url,
                session_id=session_id,
                css_selector="li.commit-item",
                extraction_strategy=extraction_strategy,
                js_code=js_next_page_and_wait if page > 0 else None,
                js_only=page > 0,
                bypass_cache=True
            )

            commits = json.loads(result.extracted_content)
            all_commits.extend(commits)
            print(f"Page {page + 1}: Found {len(commits)} commits")

        await crawler.crawler_strategy.kill_session(session_id)
        print(f"Successfully crawled {len(all_commits)} commits across 3 pages")

asyncio.run(integrated_js_and_wait_crawl())
```

This approach combines the JavaScript for clicking the "next" button and waiting for new content to load into a single script.

## Advanced Technique 3: Using the `wait_for` Parameter

Crawl4AI provides a `wait_for` parameter that allows you to specify a condition to wait for before considering the page fully loaded. This can be particularly useful for dynamic content.

Here's an example:

```python
async def wait_for_parameter_crawl():
    async with AsyncWebCrawler(verbose=True) as crawler:
        url = "https://github.com/example/repo/commits/main"
        session_id = "wait_for_session"
        all_commits = []

        js_next_page = """
        const commits = document.querySelectorAll('li.commit-item h4');
        if (commits.length > 0) {
            window.lastCommit = commits[0].textContent.trim();
        }
        const button = document.querySelector('a.pagination-next');
        if (button) button.click();
        """

        wait_for = """() => {
            const commits = document.querySelectorAll('li.commit-item h4');
            if (commits.length === 0) return false;
            const firstCommit = commits[0].textContent.trim();
            return firstCommit !== window.lastCommit;
        }"""
        
        schema = {
            "name": "Commit Extractor",
            "baseSelector": "li.commit-item",
            "fields": [
                {
                    "name": "title",
                    "selector": "h4.commit-title",
                    "type": "text",
                    "transform": "strip",
                },
            ],
        }
        extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

        for page in range(3):
            result = await crawler.arun(
                url=url,
                session_id=session_id,
                css_selector="li.commit-item",
                extraction_strategy=extraction_strategy,
                js_code=js_next_page if page > 0 else None,
                wait_for=wait_for if page > 0 else None,
                js_only=page > 0,
                bypass_cache=True
            )

            commits = json.loads(result.extracted_content)
            all_commits.extend(commits)
            print(f"Page {page + 1}: Found {len(commits)} commits")

        await crawler.crawler_strategy.kill_session(session_id)
        print(f"Successfully crawled {len(all_commits)} commits across 3 pages")

asyncio.run(wait_for_parameter_crawl())
```

This technique separates the JavaScript execution (clicking the "next" button) from the waiting condition, providing more flexibility and clarity in some scenarios.

## Best Practices for Session-Based Crawling

1. **Use Unique Session IDs**: Ensure each crawling session has a unique `session_id` to prevent conflicts.
2. **Close Sessions**: Always close sessions using `kill_session` when you're done to free up resources.
3. **Handle Errors**: Implement proper error handling to deal with unexpected situations during crawling.
4. **Respect Website Terms**: Ensure your crawling adheres to the website's terms of service and robots.txt file.
5. **Implement Delays**: Add appropriate delays between requests to avoid overwhelming the target server.
6. **Use Extraction Strategies**: Leverage `JsonCssExtractionStrategy` or other extraction strategies for structured data extraction.
7. **Optimize JavaScript**: Keep your JavaScript execution concise and efficient to improve crawling speed.
8. **Monitor Performance**: Keep an eye on memory usage and crawling speed, especially for long-running sessions.

## Conclusion

Session-based crawling with Crawl4AI provides powerful capabilities for handling dynamic content and complex web applications. By leveraging session management, JavaScript execution, and waiting strategies, you can effectively crawl and extract data from a wide range of modern websites.

Remember to use these techniques responsibly and in compliance with website policies and ethical web scraping practices.

For more advanced usage and API details, refer to the Crawl4AI API documentation.# Session Management

Session management in Crawl4AI allows you to maintain state across multiple requests and handle complex multi-page crawling tasks, particularly useful for dynamic websites.

## Basic Session Usage

Use `session_id` to maintain state between requests:

```python
async with AsyncWebCrawler() as crawler:
    session_id = "my_session"
    
    # First request
    result1 = await crawler.arun(
        url="https://example.com/page1",
        session_id=session_id
    )
    
    # Subsequent request using same session
    result2 = await crawler.arun(
        url="https://example.com/page2",
        session_id=session_id
    )
    
    # Clean up when done
    await crawler.crawler_strategy.kill_session(session_id)
```

## Dynamic Content with Sessions

Here's a real-world example of crawling GitHub commits across multiple pages:

```python
async def crawl_dynamic_content():
    async with AsyncWebCrawler(verbose=True) as crawler:
        url = "https://github.com/microsoft/TypeScript/commits/main"
        session_id = "typescript_commits_session"
        all_commits = []

        # Define navigation JavaScript
        js_next_page = """
        const button = document.querySelector('a[data-testid="pagination-next-button"]');
        if (button) button.click();
        """

        # Define wait condition
        wait_for = """() => {
            const commits = document.querySelectorAll('li.Box-sc-g0xbh4-0 h4');
            if (commits.length === 0) return false;
            const firstCommit = commits[0].textContent.trim();
            return firstCommit !== window.firstCommit;
        }"""
        
        # Define extraction schema
        schema = {
            "name": "Commit Extractor",
            "baseSelector": "li.Box-sc-g0xbh4-0",
            "fields": [
                {
                    "name": "title",
                    "selector": "h4.markdown-title",
                    "type": "text",
                    "transform": "strip",
                },
            ],
        }
        extraction_strategy = JsonCssExtractionStrategy(schema)

        # Crawl multiple pages
        for page in range(3):
            result = await crawler.arun(
                url=url,
                session_id=session_id,
                extraction_strategy=extraction_strategy,
                js_code=js_next_page if page > 0 else None,
                wait_for=wait_for if page > 0 else None,
                js_only=page > 0,
                bypass_cache=True
            )

            if result.success:
                commits = json.loads(result.extracted_content)
                all_commits.extend(commits)
                print(f"Page {page + 1}: Found {len(commits)} commits")

        # Clean up session
        await crawler.crawler_strategy.kill_session(session_id)
        return all_commits
```

## Session Best Practices

1. **Session Naming**:
```python
# Use descriptive session IDs
session_id = "login_flow_session"
session_id = "product_catalog_session"
```

2. **Resource Management**:
```python
try:
    # Your crawling code
    pass
finally:
    # Always clean up sessions
    await crawler.crawler_strategy.kill_session(session_id)
```

3. **State Management**:
```python
# First page: login
result = await crawler.arun(
    url="https://example.com/login",
    session_id=session_id,
    js_code="document.querySelector('form').submit();"
)

# Second page: verify login success
result = await crawler.arun(
    url="https://example.com/dashboard",
    session_id=session_id,
    wait_for="css:.user-profile"  # Wait for authenticated content
)
```

## Common Use Cases

1. **Authentication Flows**
2. **Pagination Handling**
3. **Form Submissions**
4. **Multi-step Processes**
5. **Dynamic Content Navigation**
## Chunking Strategies 📚

Crawl4AI provides several powerful chunking strategies to divide text into manageable parts for further processing. Each strategy has unique characteristics and is suitable for different scenarios. Let's explore them one by one.

### RegexChunking

`RegexChunking` splits text using regular expressions. This is ideal for creating chunks based on specific patterns like paragraphs or sentences.

#### When to Use
- Great for structured text with consistent delimiters.
- Suitable for documents where specific patterns (e.g., double newlines, periods) indicate logical chunks.

#### Parameters
- `patterns` (list, optional): Regular expressions used to split the text. Default is to split by double newlines (`['\n\n']`).

#### Example
```python
from crawl4ai.chunking_strategy import RegexChunking

# Define patterns for splitting text
patterns = [r'\n\n', r'\. ']
chunker = RegexChunking(patterns=patterns)

# Sample text
text = "This is a sample text. It will be split into chunks.\n\nThis is another paragraph."

# Chunk the text
chunks = chunker.chunk(text)
print(chunks)
```

### NlpSentenceChunking

`NlpSentenceChunking` uses NLP models to split text into sentences, ensuring accurate sentence boundaries.

#### When to Use
- Ideal for texts where sentence boundaries are crucial.
- Useful for creating chunks that preserve grammatical structures.

#### Parameters
- None.

#### Example
```python
from crawl4ai.chunking_strategy import NlpSentenceChunking

chunker = NlpSentenceChunking()

# Sample text
text = "This is a sample text. It will be split into sentences. Here's another sentence."

# Chunk the text
chunks = chunker.chunk(text)
print(chunks)
```

### TopicSegmentationChunking

`TopicSegmentationChunking` employs the TextTiling algorithm to segment text into topic-based chunks. This method identifies thematic boundaries.

#### When to Use
- Perfect for long documents with distinct topics.
- Useful when preserving topic continuity is more important than maintaining text order.

#### Parameters
- `num_keywords` (int, optional): Number of keywords for each topic segment. Default is `3`.

#### Example
```python
from crawl4ai.chunking_strategy import TopicSegmentationChunking

chunker = TopicSegmentationChunking(num_keywords=3)

# Sample text
text = "This document contains several topics. Topic one discusses AI. Topic two covers machine learning."

# Chunk the text
chunks = chunker.chunk(text)
print(chunks)
```

### FixedLengthWordChunking

`FixedLengthWordChunking` splits text into chunks based on a fixed number of words. This ensures each chunk has approximately the same length.

#### When to Use
- Suitable for processing large texts where uniform chunk size is important.
- Useful when the number of words per chunk needs to be controlled.

#### Parameters
- `chunk_size` (int, optional): Number of words per chunk. Default is `100`.

#### Example
```python
from crawl4ai.chunking_strategy import FixedLengthWordChunking

chunker = FixedLengthWordChunking(chunk_size=10)

# Sample text
text = "This is a sample text. It will be split into chunks of fixed length."

# Chunk the text
chunks = chunker.chunk(text)
print(chunks)
```

### SlidingWindowChunking

`SlidingWindowChunking` uses a sliding window approach to create overlapping chunks. Each chunk has a fixed length, and the window slides by a specified step size.

#### When to Use
- Ideal for creating overlapping chunks to preserve context.
- Useful for tasks where context from adjacent chunks is needed.

#### Parameters
- `window_size` (int, optional): Number of words in each chunk. Default is `100`.
- `step` (int, optional): Number of words to slide the window. Default is `50`.

#### Example
```python
from crawl4ai.chunking_strategy import SlidingWindowChunking

chunker = SlidingWindowChunking(window_size=10, step=5)

# Sample text
text = "This is a sample text. It will be split using a sliding window approach to preserve context."

# Chunk the text
chunks = chunker.chunk(text)
print(chunks)
```

With these chunking strategies, you can choose the best method to divide your text based on your specific needs. Whether you need precise sentence boundaries, topic-based segmentation, or uniform chunk sizes, Crawl4AI has you covered. Happy chunking! 📝✨
# Cosine Strategy

The Cosine Strategy in Crawl4AI uses similarity-based clustering to identify and extract relevant content sections from web pages. This strategy is particularly useful when you need to find and extract content based on semantic similarity rather than structural patterns.

## How It Works

The Cosine Strategy:
1. Breaks down page content into meaningful chunks
2. Converts text into vector representations
3. Calculates similarity between chunks
4. Clusters similar content together
5. Ranks and filters content based on relevance

## Basic Usage

```python
from crawl4ai.extraction_strategy import CosineStrategy

strategy = CosineStrategy(
    semantic_filter="product reviews",    # Target content type
    word_count_threshold=10,             # Minimum words per cluster
    sim_threshold=0.3                    # Similarity threshold
)

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url="https://example.com/reviews",
        extraction_strategy=strategy
    )
    
    content = result.extracted_content
```

## Configuration Options

### Core Parameters

```python
CosineStrategy(
    # Content Filtering
    semantic_filter: str = None,       # Keywords/topic for content filtering
    word_count_threshold: int = 10,    # Minimum words per cluster
    sim_threshold: float = 0.3,        # Similarity threshold (0.0 to 1.0)
    
    # Clustering Parameters
    max_dist: float = 0.2,            # Maximum distance for clustering
    linkage_method: str = 'ward',      # Clustering linkage method
    top_k: int = 3,                   # Number of top categories to extract
    
    # Model Configuration
    model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',  # Embedding model
    
    verbose: bool = False             # Enable logging
)
```

### Parameter Details

1. **semantic_filter**
   - Sets the target topic or content type
   - Use keywords relevant to your desired content
   - Example: "technical specifications", "user reviews", "pricing information"

2. **sim_threshold**
   - Controls how similar content must be to be grouped together
   - Higher values (e.g., 0.8) mean stricter matching
   - Lower values (e.g., 0.3) allow more variation
   ```python
   # Strict matching
   strategy = CosineStrategy(sim_threshold=0.8)
   
   # Loose matching
   strategy = CosineStrategy(sim_threshold=0.3)
   ```

3. **word_count_threshold**
   - Filters out short content blocks
   - Helps eliminate noise and irrelevant content
   ```python
   # Only consider substantial paragraphs
   strategy = CosineStrategy(word_count_threshold=50)
   ```

4. **top_k**
   - Number of top content clusters to return
   - Higher values return more diverse content
   ```python
   # Get top 5 most relevant content clusters
   strategy = CosineStrategy(top_k=5)
   ```

## Use Cases

### 1. Article Content Extraction
```python
strategy = CosineStrategy(
    semantic_filter="main article content",
    word_count_threshold=100,  # Longer blocks for articles
    top_k=1                   # Usually want single main content
)

result = await crawler.arun(
    url="https://example.com/blog/post",
    extraction_strategy=strategy
)
```

### 2. Product Review Analysis
```python
strategy = CosineStrategy(
    semantic_filter="customer reviews and ratings",
    word_count_threshold=20,   # Reviews can be shorter
    top_k=10,                 # Get multiple reviews
    sim_threshold=0.4         # Allow variety in review content
)
```

### 3. Technical Documentation
```python
strategy = CosineStrategy(
    semantic_filter="technical specifications documentation",
    word_count_threshold=30,
    sim_threshold=0.6,        # Stricter matching for technical content
    max_dist=0.3             # Allow related technical sections
)
```

## Advanced Features

### Custom Clustering
```python
strategy = CosineStrategy(
    linkage_method='complete',  # Alternative clustering method
    max_dist=0.4,              # Larger clusters
    model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'  # Multilingual support
)
```

### Content Filtering Pipeline
```python
strategy = CosineStrategy(
    semantic_filter="pricing plans features",
    word_count_threshold=15,
    sim_threshold=0.5,
    top_k=3
)

async def extract_pricing_features(url: str):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            extraction_strategy=strategy
        )
        
        if result.success:
            content = json.loads(result.extracted_content)
            return {
                'pricing_features': content,
                'clusters': len(content),
                'similarity_scores': [item['score'] for item in content]
            }
```

## Best Practices

1. **Adjust Thresholds Iteratively**
   - Start with default values
   - Adjust based on results
   - Monitor clustering quality

2. **Choose Appropriate Word Count Thresholds**
   - Higher for articles (100+)
   - Lower for reviews/comments (20+)
   - Medium for product descriptions (50+)

3. **Optimize Performance**
   ```python
   strategy = CosineStrategy(
       word_count_threshold=10,  # Filter early
       top_k=5,                 # Limit results
       verbose=True             # Monitor performance
   )
   ```

4. **Handle Different Content Types**
   ```python
   # For mixed content pages
   strategy = CosineStrategy(
       semantic_filter="product features",
       sim_threshold=0.4,      # More flexible matching
       max_dist=0.3,          # Larger clusters
       top_k=3                # Multiple relevant sections
   )
   ```

## Error Handling

```python
try:
    result = await crawler.arun(
        url="https://example.com",
        extraction_strategy=strategy
    )
    
    if result.success:
        content = json.loads(result.extracted_content)
        if not content:
            print("No relevant content found")
    else:
        print(f"Extraction failed: {result.error_message}")
        
except Exception as e:
    print(f"Error during extraction: {str(e)}")
```

The Cosine Strategy is particularly effective when:
- Content structure is inconsistent
- You need semantic understanding
- You want to find similar content blocks
- Structure-based extraction (CSS/XPath) isn't reliable

It works well with other strategies and can be used as a pre-processing step for LLM-based extraction.# Advanced Usage of JsonCssExtractionStrategy

While the basic usage of JsonCssExtractionStrategy is powerful for simple structures, its true potential shines when dealing with complex, nested HTML structures. This section will explore advanced usage scenarios, demonstrating how to extract nested objects, lists, and nested lists.

## Hypothetical Website Example

Let's consider a hypothetical e-commerce website that displays product categories, each containing multiple products. Each product has details, reviews, and related items. This complex structure will allow us to demonstrate various advanced features of JsonCssExtractionStrategy.

Assume the HTML structure looks something like this:

```html
<div class="category">
  <h2 class="category-name">Electronics</h2>
  <div class="product">
    <h3 class="product-name">Smartphone X</h3>
    <p class="product-price">$999</p>
    <div class="product-details">
      <span class="brand">TechCorp</span>
      <span class="model">X-2000</span>
    </div>
    <ul class="product-features">
      <li>5G capable</li>
      <li>6.5" OLED screen</li>
      <li>128GB storage</li>
    </ul>
    <div class="product-reviews">
      <div class="review">
        <span class="reviewer">John D.</span>
        <span class="rating">4.5</span>
        <p class="review-text">Great phone, love the camera!</p>
      </div>
      <div class="review">
        <span class="reviewer">Jane S.</span>
        <span class="rating">5</span>
        <p class="review-text">Best smartphone I've ever owned.</p>
      </div>
    </div>
    <ul class="related-products">
      <li>
        <span class="related-name">Phone Case</span>
        <span class="related-price">$29.99</span>
      </li>
      <li>
        <span class="related-name">Screen Protector</span>
        <span class="related-price">$9.99</span>
      </li>
    </ul>
  </div>
  <!-- More products... -->
</div>
```

Now, let's create a schema to extract this complex structure:

```python
schema = {
    "name": "E-commerce Product Catalog",
    "baseSelector": "div.category",
    "fields": [
        {
            "name": "category_name",
            "selector": "h2.category-name",
            "type": "text"
        },
        {
            "name": "products",
            "selector": "div.product",
            "type": "nested_list",
            "fields": [
                {
                    "name": "name",
                    "selector": "h3.product-name",
                    "type": "text"
                },
                {
                    "name": "price",
                    "selector": "p.product-price",
                    "type": "text"
                },
                {
                    "name": "details",
                    "selector": "div.product-details",
                    "type": "nested",
                    "fields": [
                        {
                            "name": "brand",
                            "selector": "span.brand",
                            "type": "text"
                        },
                        {
                            "name": "model",
                            "selector": "span.model",
                            "type": "text"
                        }
                    ]
                },
                {
                    "name": "features",
                    "selector": "ul.product-features li",
                    "type": "list",
                    "fields": [
                        {
                            "name": "feature",
                            "type": "text"
                        }
                    ]
                },
                {
                    "name": "reviews",
                    "selector": "div.review",
                    "type": "nested_list",
                    "fields": [
                        {
                            "name": "reviewer",
                            "selector": "span.reviewer",
                            "type": "text"
                        },
                        {
                            "name": "rating",
                            "selector": "span.rating",
                            "type": "text"
                        },
                        {
                            "name": "comment",
                            "selector": "p.review-text",
                            "type": "text"
                        }
                    ]
                },
                {
                    "name": "related_products",
                    "selector": "ul.related-products li",
                    "type": "list",
                    "fields": [
                        {
                            "name": "name",
                            "selector": "span.related-name",
                            "type": "text"
                        },
                        {
                            "name": "price",
                            "selector": "span.related-price",
                            "type": "text"
                        }
                    ]
                }
            ]
        }
    ]
}
```

This schema demonstrates several advanced features:

1. **Nested Objects**: The `details` field is a nested object within each product.
2. **Simple Lists**: The `features` field is a simple list of text items.
3. **Nested Lists**: The `products` field is a nested list, where each item is a complex object.
4. **Lists of Objects**: The `reviews` and `related_products` fields are lists of objects.

Let's break down the key concepts:

### Nested Objects

To create a nested object, use `"type": "nested"` and provide a `fields` array for the nested structure:

```python
{
    "name": "details",
    "selector": "div.product-details",
    "type": "nested",
    "fields": [
        {
            "name": "brand",
            "selector": "span.brand",
            "type": "text"
        },
        {
            "name": "model",
            "selector": "span.model",
            "type": "text"
        }
    ]
}
```

### Simple Lists

For a simple list of identical items, use `"type": "list"`:

```python
{
    "name": "features",
    "selector": "ul.product-features li",
    "type": "list",
    "fields": [
        {
            "name": "feature",
            "type": "text"
        }
    ]
}
```

### Nested Lists

For a list of complex objects, use `"type": "nested_list"`:

```python
{
    "name": "products",
    "selector": "div.product",
    "type": "nested_list",
    "fields": [
        // ... fields for each product
    ]
}
```

### Lists of Objects

Similar to nested lists, but typically used for simpler objects within the list:

```python
{
    "name": "related_products",
    "selector": "ul.related-products li",
    "type": "list",
    "fields": [
        {
            "name": "name",
            "selector": "span.related-name",
            "type": "text"
        },
        {
            "name": "price",
            "selector": "span.related-price",
            "type": "text"
        }
    ]
}
```

## Using the Advanced Schema

To use this advanced schema with AsyncWebCrawler:

```python
import json
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

async def extract_complex_product_data():
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://gist.githubusercontent.com/githubusercontent/2d7b8ba3cd8ab6cf3c8da771ddb36878/raw/1ae2f90c6861ce7dd84cc50d3df9920dee5e1fd2/sample_ecommerce.html",
            extraction_strategy=extraction_strategy,
            bypass_cache=True,
        )

        assert result.success, "Failed to crawl the page"

        product_data = json.loads(result.extracted_content)
        print(json.dumps(product_data, indent=2))

asyncio.run(extract_complex_product_data())
```

This will produce a structured JSON output that captures the complex hierarchy of the product catalog, including nested objects, lists, and nested lists.

## Tips for Advanced Usage

1. **Start Simple**: Begin with a basic schema and gradually add complexity.
2. **Test Incrementally**: Test each part of your schema separately before combining them.
3. **Use Chrome DevTools**: The Element Inspector is invaluable for identifying the correct selectors.
4. **Handle Missing Data**: Use the `default` key in your field definitions to handle cases where data might be missing.
5. **Leverage Transforms**: Use the `transform` key to clean or format extracted data (e.g., converting prices to numbers).
6. **Consider Performance**: Very complex schemas might slow down extraction. Balance complexity with performance needs.

By mastering these advanced techniques, you can use JsonCssExtractionStrategy to extract highly structured data from even the most complex web pages, making it a powerful tool for web scraping and data analysis tasks.# JSON CSS Extraction Strategy with AsyncWebCrawler

The `JsonCssExtractionStrategy` is a powerful feature of Crawl4AI that allows you to extract structured data from web pages using CSS selectors. This method is particularly useful when you need to extract specific data points from a consistent HTML structure, such as tables or repeated elements. Here's how to use it with the AsyncWebCrawler.

## Overview

The `JsonCssExtractionStrategy` works by defining a schema that specifies:
1. A base CSS selector for the repeating elements
2. Fields to extract from each element, each with its own CSS selector

This strategy is fast and efficient, as it doesn't rely on external services like LLMs for extraction.

## Example: Extracting Cryptocurrency Prices from Coinbase

Let's look at an example that extracts cryptocurrency prices from the Coinbase explore page.

```python
import json
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

async def extract_structured_data_using_css_extractor():
    print("\n--- Using JsonCssExtractionStrategy for Fast Structured Output ---")
    
    # Define the extraction schema
    schema = {
        "name": "Coinbase Crypto Prices",
        "baseSelector": ".cds-tableRow-t45thuk",
        "fields": [
            {
                "name": "crypto",
                "selector": "td:nth-child(1) h2",
                "type": "text",
            },
            {
                "name": "symbol",
                "selector": "td:nth-child(1) p",
                "type": "text",
            },
            {
                "name": "price",
                "selector": "td:nth-child(2)",
                "type": "text",
            }
        ],
    }

    # Create the extraction strategy
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

    # Use the AsyncWebCrawler with the extraction strategy
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://www.coinbase.com/explore",
            extraction_strategy=extraction_strategy,
            bypass_cache=True,
        )

        assert result.success, "Failed to crawl the page"

        # Parse the extracted content
        crypto_prices = json.loads(result.extracted_content)
        print(f"Successfully extracted {len(crypto_prices)} cryptocurrency prices")
        print(json.dumps(crypto_prices[0], indent=2))

    return crypto_prices

# Run the async function
asyncio.run(extract_structured_data_using_css_extractor())
```

## Explanation of the Schema

The schema defines how to extract the data:

- `name`: A descriptive name for the extraction task.
- `baseSelector`: The CSS selector for the repeating elements (in this case, table rows).
- `fields`: An array of fields to extract from each element:
  - `name`: The name to give the extracted data.
  - `selector`: The CSS selector to find the specific data within the base element.
  - `type`: The type of data to extract (usually "text" for textual content).

## Advantages of JsonCssExtractionStrategy

1. **Speed**: CSS selectors are fast to execute, making this method efficient for large datasets.
2. **Precision**: You can target exactly the elements you need.
3. **Structured Output**: The result is already structured as JSON, ready for further processing.
4. **No External Dependencies**: Unlike LLM-based strategies, this doesn't require any API calls to external services.

## Tips for Using JsonCssExtractionStrategy

1. **Inspect the Page**: Use browser developer tools to identify the correct CSS selectors.
2. **Test Selectors**: Verify your selectors in the browser console before using them in the script.
3. **Handle Dynamic Content**: If the page uses JavaScript to load content, you may need to combine this with JS execution (see the Advanced Usage section).
4. **Error Handling**: Always check the `result.success` flag and handle potential failures.

## Advanced Usage: Combining with JavaScript Execution

For pages that load data dynamically, you can combine the `JsonCssExtractionStrategy` with JavaScript execution:

```python
async def extract_dynamic_structured_data():
    schema = {
        "name": "Dynamic Crypto Prices",
        "baseSelector": ".crypto-row",
        "fields": [
            {"name": "name", "selector": ".crypto-name", "type": "text"},
            {"name": "price", "selector": ".crypto-price", "type": "text"},
        ]
    }

    js_code = """
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(resolve => setTimeout(resolve, 2000));  // Wait for 2 seconds
    """

    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://example.com/crypto-prices",
            extraction_strategy=extraction_strategy,
            js_code=js_code,
            wait_for=".crypto-row:nth-child(20)",  # Wait for 20 rows to load
            bypass_cache=True,
        )

        crypto_data = json.loads(result.extracted_content)
        print(f"Extracted {len(crypto_data)} cryptocurrency entries")

asyncio.run(extract_dynamic_structured_data())
```

This advanced example demonstrates how to:
1. Execute JavaScript to trigger dynamic content loading.
2. Wait for a specific condition (20 rows loaded) before extraction.
3. Extract data from the dynamically loaded content.

By mastering the `JsonCssExtractionStrategy`, you can efficiently extract structured data from a wide variety of web pages, making it a valuable tool in your web scraping toolkit.

For more details on schema definitions and advanced extraction strategies, check out the[Advanced JsonCssExtraction](./css-advanced.md).# LLM Extraction with AsyncWebCrawler

Crawl4AI's AsyncWebCrawler allows you to use Language Models (LLMs) to extract structured data or relevant content from web pages asynchronously. Below are two examples demonstrating how to use `LLMExtractionStrategy` for different purposes with the AsyncWebCrawler.

## Example 1: Extract Structured Data

In this example, we use the `LLMExtractionStrategy` to extract structured data (model names and their fees) from the OpenAI pricing page.

```python
import os
import json
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel, Field

class OpenAIModelFee(BaseModel):
    model_name: str = Field(..., description="Name of the OpenAI model.")
    input_fee: str = Field(..., description="Fee for input token for the OpenAI model.")
    output_fee: str = Field(..., description="Fee for output token for the OpenAI model.")

async def extract_openai_fees():
    url = 'https://openai.com/api/pricing/'

    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=url,
            word_count_threshold=1,
            extraction_strategy=LLMExtractionStrategy(
                provider="openai/gpt-4o", # Or use ollama like provider="ollama/nemotron"
                api_token=os.getenv('OPENAI_API_KEY'),
                schema=OpenAIModelFee.model_json_schema(),
                extraction_type="schema",
                instruction="From the crawled content, extract all mentioned model names along with their "
                            "fees for input and output tokens. Make sure not to miss anything in the entire content. "
                            'One extracted model JSON format should look like this: '
                            '{ "model_name": "GPT-4", "input_fee": "US$10.00 / 1M tokens", "output_fee": "US$30.00 / 1M tokens" }'
            ),
            bypass_cache=True,
        )

    model_fees = json.loads(result.extracted_content)
    print(f"Number of models extracted: {len(model_fees)}")

    with open(".data/openai_fees.json", "w", encoding="utf-8") as f:
        json.dump(model_fees, f, indent=2)

asyncio.run(extract_openai_fees())
```

## Example 2: Extract Relevant Content

In this example, we instruct the LLM to extract only content related to technology from the NBC News business page.

```python
import os
import json
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy

async def extract_tech_content():
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://www.nbcnews.com/business",
            extraction_strategy=LLMExtractionStrategy(
                provider="openai/gpt-4o",
                api_token=os.getenv('OPENAI_API_KEY'),
                instruction="Extract only content related to technology"
            ),
            bypass_cache=True,
        )

    tech_content = json.loads(result.extracted_content)
    print(f"Number of tech-related items extracted: {len(tech_content)}")

    with open(".data/tech_content.json", "w", encoding="utf-8") as f:
        json.dump(tech_content, f, indent=2)

asyncio.run(extract_tech_content())
```

## Advanced Usage: Combining JS Execution with LLM Extraction

This example demonstrates how to combine JavaScript execution with LLM extraction to handle dynamic content:

```python
async def extract_dynamic_content():
    js_code = """
    const loadMoreButton = Array.from(document.querySelectorAll('button')).find(button => button.textContent.includes('Load More'));
    if (loadMoreButton) {
        loadMoreButton.click();
        await new Promise(resolve => setTimeout(resolve, 2000));
    }
    """

    wait_for = """
    () => {
        const articles = document.querySelectorAll('article.tease-card');
        return articles.length > 10;
    }
    """

    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://www.nbcnews.com/business",
            js_code=js_code,
            wait_for=wait_for,
            css_selector="article.tease-card",
            extraction_strategy=LLMExtractionStrategy(
                provider="openai/gpt-4o",
                api_token=os.getenv('OPENAI_API_KEY'),
                instruction="Summarize each article, focusing on technology-related content"
            ),
            bypass_cache=True,
        )

    summaries = json.loads(result.extracted_content)
    print(f"Number of summarized articles: {len(summaries)}")

    with open(".data/tech_summaries.json", "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)

asyncio.run(extract_dynamic_content())
```

## Customizing LLM Provider

Crawl4AI uses the `litellm` library under the hood, which allows you to use any LLM provider you want. Just pass the correct model name and API token:

```python
extraction_strategy=LLMExtractionStrategy(
    provider="your_llm_provider/model_name",
    api_token="your_api_token",
    instruction="Your extraction instruction"
)
```

This flexibility allows you to integrate with various LLM providers and tailor the extraction process to your specific needs.

## Error Handling and Retries

When working with external LLM APIs, it's important to handle potential errors and implement retry logic. Here's an example of how you might do this:

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class LLMExtractionError(Exception):
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def extract_with_retry(crawler, url, extraction_strategy):
    try:
        result = await crawler.arun(url=url, extraction_strategy=extraction_strategy, bypass_cache=True)
        return json.loads(result.extracted_content)
    except Exception as e:
        raise LLMExtractionError(f"Failed to extract content: {str(e)}")

async def main():
    async with AsyncWebCrawler(verbose=True) as crawler:
        try:
            content = await extract_with_retry(
                crawler,
                "https://www.example.com",
                LLMExtractionStrategy(
                    provider="openai/gpt-4o",
                    api_token=os.getenv('OPENAI_API_KEY'),
                    instruction="Extract and summarize main points"
                )
            )
            print("Extracted content:", content)
        except LLMExtractionError as e:
            print(f"Extraction failed after retries: {e}")

asyncio.run(main())
```

This example uses the `tenacity` library to implement a retry mechanism with exponential backoff, which can help handle temporary failures or rate limiting from the LLM API.# Extraction Strategies Overview

Crawl4AI provides powerful extraction strategies to help you get structured data from web pages. Each strategy is designed for specific use cases and offers different approaches to data extraction.

## Available Strategies

### [LLM-Based Extraction](llm.md)

`LLMExtractionStrategy` uses Language Models to extract structured data from web content. This approach is highly flexible and can understand content semantically.

```python
from pydantic import BaseModel
from crawl4ai.extraction_strategy import LLMExtractionStrategy

class Product(BaseModel):
    name: str
    price: float
    description: str

strategy = LLMExtractionStrategy(
    provider="ollama/llama2",
    schema=Product.schema(),
    instruction="Extract product details from the page"
)

result = await crawler.arun(
    url="https://example.com/product",
    extraction_strategy=strategy
)
```

**Best for:**
- Complex data structures
- Content requiring interpretation
- Flexible content formats
- Natural language processing

### [CSS-Based Extraction](css.md)

`JsonCssExtractionStrategy` extracts data using CSS selectors. This is fast, reliable, and perfect for consistently structured pages.

```python
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

schema = {
    "name": "Product Listing",
    "baseSelector": ".product-card",
    "fields": [
        {"name": "title", "selector": "h2", "type": "text"},
        {"name": "price", "selector": ".price", "type": "text"},
        {"name": "image", "selector": "img", "type": "attribute", "attribute": "src"}
    ]
}

strategy = JsonCssExtractionStrategy(schema)

result = await crawler.arun(
    url="https://example.com/products",
    extraction_strategy=strategy
)
```

**Best for:**
- E-commerce product listings
- News article collections
- Structured content pages
- High-performance needs

### [Cosine Strategy](cosine.md)

`CosineStrategy` uses similarity-based clustering to identify and extract relevant content sections.

```python
from crawl4ai.extraction_strategy import CosineStrategy

strategy = CosineStrategy(
    semantic_filter="product reviews",    # Content focus
    word_count_threshold=10,             # Minimum words per cluster
    sim_threshold=0.3,                   # Similarity threshold
    max_dist=0.2,                        # Maximum cluster distance
    top_k=3                             # Number of top clusters to extract
)

result = await crawler.arun(
    url="https://example.com/reviews",
    extraction_strategy=strategy
)
```

**Best for:**
- Content similarity analysis
- Topic clustering
- Relevant content extraction
- Pattern recognition in text

## Strategy Selection Guide

Choose your strategy based on these factors:

1. **Content Structure**
   - Well-structured HTML → Use CSS Strategy
   - Natural language text → Use LLM Strategy
   - Mixed/Complex content → Use Cosine Strategy

2. **Performance Requirements**
   - Fastest: CSS Strategy
   - Moderate: Cosine Strategy
   - Variable: LLM Strategy (depends on provider)

3. **Accuracy Needs**
   - Highest structure accuracy: CSS Strategy
   - Best semantic understanding: LLM Strategy
   - Best content relevance: Cosine Strategy

## Combining Strategies

You can combine strategies for more powerful extraction:

```python
# First use CSS strategy for initial structure
css_result = await crawler.arun(
    url="https://example.com",
    extraction_strategy=css_strategy
)

# Then use LLM for semantic analysis
llm_result = await crawler.arun(
    url="https://example.com",
    extraction_strategy=llm_strategy
)
```

## Common Use Cases

1. **E-commerce Scraping**
   ```python
   # CSS Strategy for product listings
   schema = {
       "name": "Products",
       "baseSelector": ".product",
       "fields": [
           {"name": "name", "selector": ".title", "type": "text"},
           {"name": "price", "selector": ".price", "type": "text"}
       ]
   }
   ```

2. **News Article Extraction**
   ```python
   # LLM Strategy for article content
   class Article(BaseModel):
       title: str
       content: str
       author: str
       date: str

   strategy = LLMExtractionStrategy(
       provider="ollama/llama2",
       schema=Article.schema()
   )
   ```

3. **Content Analysis**
   ```python
   # Cosine Strategy for topic analysis
   strategy = CosineStrategy(
       semantic_filter="technology trends",
       top_k=5
   )
   ```

## Best Practices

1. **Choose the Right Strategy**
   - Start with CSS for structured data
   - Use LLM for complex interpretation
   - Try Cosine for content relevance

2. **Optimize Performance**
   - Cache LLM results
   - Keep CSS selectors specific
   - Tune similarity thresholds

3. **Handle Errors**
   ```python
   result = await crawler.arun(
       url="https://example.com",
       extraction_strategy=strategy
   )
   
   if not result.success:
       print(f"Extraction failed: {result.error_message}")
   else:
       data = json.loads(result.extracted_content)
   ```

Each strategy has its strengths and optimal use cases. Explore the detailed documentation for each strategy to learn more about their specific features and configurations.# AsyncWebCrawler

The `AsyncWebCrawler` class is the main interface for web crawling operations. It provides asynchronous web crawling capabilities with extensive configuration options.

## Constructor

```python
AsyncWebCrawler(
    # Browser Settings
    browser_type: str = "chromium",         # Options: "chromium", "firefox", "webkit"
    headless: bool = True,                  # Run browser in headless mode
    verbose: bool = False,                  # Enable verbose logging
    
    # Cache Settings
    always_by_pass_cache: bool = False,     # Always bypass cache
    base_directory: str = str(Path.home()), # Base directory for cache
    
    # Network Settings
    proxy: str = None,                      # Simple proxy URL
    proxy_config: Dict = None,              # Advanced proxy configuration
    
    # Browser Behavior
    sleep_on_close: bool = False,           # Wait before closing browser
    
    # Custom Settings
    user_agent: str = None,                 # Custom user agent
    headers: Dict[str, str] = {},           # Custom HTTP headers
    js_code: Union[str, List[str]] = None,  # Default JavaScript to execute
)
```

### Parameters in Detail

#### Browser Settings

- **browser_type** (str, optional)
  - Default: `"chromium"`
  - Options: `"chromium"`, `"firefox"`, `"webkit"`
  - Controls which browser engine to use
  ```python
  # Example: Using Firefox
  crawler = AsyncWebCrawler(browser_type="firefox")
  ```

- **headless** (bool, optional)
  - Default: `True`
  - When `True`, browser runs without GUI
  - Set to `False` for debugging
  ```python
  # Visible browser for debugging
  crawler = AsyncWebCrawler(headless=False)
  ```

- **verbose** (bool, optional)
  - Default: `False`
  - Enables detailed logging
  ```python
  # Enable detailed logging
  crawler = AsyncWebCrawler(verbose=True)
  ```

#### Cache Settings

- **always_by_pass_cache** (bool, optional)
  - Default: `False`
  - When `True`, always fetches fresh content
  ```python
  # Always fetch fresh content
  crawler = AsyncWebCrawler(always_by_pass_cache=True)
  ```

- **base_directory** (str, optional)
  - Default: User's home directory
  - Base path for cache storage
  ```python
  # Custom cache directory
  crawler = AsyncWebCrawler(base_directory="/path/to/cache")
  ```

#### Network Settings

- **proxy** (str, optional)
  - Simple proxy URL
  ```python
  # Using simple proxy
  crawler = AsyncWebCrawler(proxy="http://proxy.example.com:8080")
  ```

- **proxy_config** (Dict, optional)
  - Advanced proxy configuration with authentication
  ```python
  # Advanced proxy with auth
  crawler = AsyncWebCrawler(proxy_config={
      "server": "http://proxy.example.com:8080",
      "username": "user",
      "password": "pass"
  })
  ```

#### Browser Behavior

- **sleep_on_close** (bool, optional)
  - Default: `False`
  - Adds delay before closing browser
  ```python
  # Wait before closing
  crawler = AsyncWebCrawler(sleep_on_close=True)
  ```

#### Custom Settings

- **user_agent** (str, optional)
  - Custom user agent string
  ```python
  # Custom user agent
  crawler = AsyncWebCrawler(
      user_agent="Mozilla/5.0 (Custom Agent) Chrome/90.0"
  )
  ```

- **headers** (Dict[str, str], optional)
  - Custom HTTP headers
  ```python
  # Custom headers
  crawler = AsyncWebCrawler(
      headers={
          "Accept-Language": "en-US",
          "Custom-Header": "Value"
      }
  )
  ```

- **js_code** (Union[str, List[str]], optional)
  - Default JavaScript to execute on each page
  ```python
  # Default JavaScript
  crawler = AsyncWebCrawler(
      js_code=[
          "window.scrollTo(0, document.body.scrollHeight);",
          "document.querySelector('.load-more').click();"
      ]
  )
  ```

## Methods

### arun()

The primary method for crawling web pages.

```python
async def arun(
    # Required
    url: str,                              # URL to crawl
    
    # Content Selection
    css_selector: str = None,              # CSS selector for content
    word_count_threshold: int = 10,        # Minimum words per block
    
    # Cache Control
    bypass_cache: bool = False,            # Bypass cache for this request
    
    # Session Management
    session_id: str = None,                # Session identifier
    
    # Screenshot Options
    screenshot: bool = False,              # Take screenshot
    screenshot_wait_for: float = None,     # Wait before screenshot
    
    # Content Processing
    process_iframes: bool = False,         # Process iframe content
    remove_overlay_elements: bool = False, # Remove popups/modals
    
    # Anti-Bot Settings
    simulate_user: bool = False,           # Simulate human behavior
    override_navigator: bool = False,      # Override navigator properties
    magic: bool = False,                   # Enable all anti-detection
    
    # Content Filtering
    excluded_tags: List[str] = None,       # HTML tags to exclude
    exclude_external_links: bool = False,  # Remove external links
    exclude_social_media_links: bool = False, # Remove social media links
    
    # JavaScript Handling
    js_code: Union[str, List[str]] = None, # JavaScript to execute
    wait_for: str = None,                  # Wait condition
    
    # Page Loading
    page_timeout: int = 60000,            # Page load timeout (ms)
    delay_before_return_html: float = None, # Wait before return
    
    # Extraction
    extraction_strategy: ExtractionStrategy = None  # Extraction strategy
) -> CrawlResult:
```

### Usage Examples

#### Basic Crawling
```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url="https://example.com")
```

#### Advanced Crawling
```python
async with AsyncWebCrawler(
    browser_type="firefox",
    verbose=True,
    headers={"Custom-Header": "Value"}
) as crawler:
    result = await crawler.arun(
        url="https://example.com",
        css_selector=".main-content",
        word_count_threshold=20,
        process_iframes=True,
        magic=True,
        wait_for="css:.dynamic-content",
        screenshot=True
    )
```

#### Session Management
```python
async with AsyncWebCrawler() as crawler:
    # First request
    result1 = await crawler.arun(
        url="https://example.com/login",
        session_id="my_session"
    )
    
    # Subsequent request using same session
    result2 = await crawler.arun(
        url="https://example.com/protected",
        session_id="my_session"
    )
```

## Context Manager

AsyncWebCrawler implements the async context manager protocol:

```python
async def __aenter__(self) -> 'AsyncWebCrawler':
    # Initialize browser and resources
    return self

async def __aexit__(self, *args):
    # Cleanup resources
    pass
```

Always use AsyncWebCrawler with async context manager:
```python
async with AsyncWebCrawler() as crawler:
    # Your crawling code here
    pass
```

## Best Practices

1. **Resource Management**
```python
# Always use context manager
async with AsyncWebCrawler() as crawler:
    # Crawler will be properly cleaned up
    pass
```

2. **Error Handling**
```python
try:
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url="https://example.com")
        if not result.success:
            print(f"Crawl failed: {result.error_message}")
except Exception as e:
    print(f"Error: {str(e)}")
```

3. **Performance Optimization**
```python
# Enable caching for better performance
crawler = AsyncWebCrawler(
    always_by_pass_cache=False,
    verbose=True
)
```

4. **Anti-Detection**
```python
# Maximum stealth
crawler = AsyncWebCrawler(
    headless=True,
    user_agent="Mozilla/5.0...",
    headers={"Accept-Language": "en-US"}
)
result = await crawler.arun(
    url="https://example.com",
    magic=True,
    simulate_user=True
)
```

## Note on Browser Types

Each browser type has its characteristics:

- **chromium**: Best overall compatibility
- **firefox**: Good for specific use cases
- **webkit**: Lighter weight, good for basic crawling

Choose based on your specific needs:
```python
# High compatibility
crawler = AsyncWebCrawler(browser_type="chromium")

# Memory efficient
crawler = AsyncWebCrawler(browser_type="webkit")
```


# Complete Parameter Guide for arun()

The following parameters can be passed to the `arun()` method. They are organized by their primary usage context and functionality.

## Core Parameters

```python
await crawler.arun(
    url="https://example.com",   # Required: URL to crawl
    verbose=True,               # Enable detailed logging
    bypass_cache=False,         # Skip cache for this request
    warmup=True                # Whether to run warmup check
)
```

## Content Processing Parameters

### Text Processing
```python
await crawler.arun(
    word_count_threshold=10,                # Minimum words per content block
    image_description_min_word_threshold=5,  # Minimum words for image descriptions
    only_text=False,                        # Extract only text content
    excluded_tags=['form', 'nav'],          # HTML tags to exclude
    keep_data_attributes=False,             # Preserve data-* attributes
)
```

### Content Selection
```python
await crawler.arun(
    css_selector=".main-content",  # CSS selector for content extraction
    remove_forms=True,             # Remove all form elements
    remove_overlay_elements=True,  # Remove popups/modals/overlays
)
```

### Link Handling
```python
await crawler.arun(
    exclude_external_links=True,          # Remove external links
    exclude_social_media_links=True,      # Remove social media links
    exclude_external_images=True,         # Remove external images
    exclude_domains=["ads.example.com"],  # Specific domains to exclude
    social_media_domains=[               # Additional social media domains
        "facebook.com",
        "twitter.com",
        "instagram.com"
    ]
)
```

## Browser Control Parameters

### Basic Browser Settings
```python
await crawler.arun(
    headless=True,                # Run browser in headless mode
    browser_type="chromium",      # Browser engine: "chromium", "firefox", "webkit"
    page_timeout=60000,          # Page load timeout in milliseconds
    user_agent="custom-agent",    # Custom user agent
)
```

### Navigation and Waiting
```python
await crawler.arun(
    wait_for="css:.dynamic-content",  # Wait for element/condition
    delay_before_return_html=2.0,     # Wait before returning HTML (seconds)
)
```

### JavaScript Execution
```python
await crawler.arun(
    js_code=[                     # JavaScript to execute (string or list)
        "window.scrollTo(0, document.body.scrollHeight);",
        "document.querySelector('.load-more').click();"
    ],
    js_only=False,               # Only execute JavaScript without reloading page
)
```

### Anti-Bot Features
```python
await crawler.arun(
    magic=True,              # Enable all anti-detection features
    simulate_user=True,      # Simulate human behavior
    override_navigator=True  # Override navigator properties
)
```

### Session Management
```python
await crawler.arun(
    session_id="my_session",  # Session identifier for persistent browsing
)
```

### Screenshot Options
```python
await crawler.arun(
    screenshot=True,              # Take page screenshot
    screenshot_wait_for=2.0,      # Wait before screenshot (seconds)
)
```

### Proxy Configuration
```python
await crawler.arun(
    proxy="http://proxy.example.com:8080",     # Simple proxy URL
    proxy_config={                             # Advanced proxy settings
        "server": "http://proxy.example.com:8080",
        "username": "user",
        "password": "pass"
    }
)
```

## Content Extraction Parameters

### Extraction Strategy
```python
await crawler.arun(
    extraction_strategy=LLMExtractionStrategy(
        provider="ollama/llama2",
        schema=MySchema.schema(),
        instruction="Extract specific data"
    )
)
```

### Chunking Strategy
```python
await crawler.arun(
    chunking_strategy=RegexChunking(
        patterns=[r'\n\n', r'\.\s+']
    )
)
```

### HTML to Text Options
```python
await crawler.arun(
    html2text={
        "ignore_links": False,
        "ignore_images": False,
        "escape_dot": False,
        "body_width": 0,
        "protect_links": True,
        "unicode_snob": True
    }
)
```

## Debug Options
```python
await crawler.arun(
    log_console=True,   # Log browser console messages
)
```

## Parameter Interactions and Notes

1. **Magic Mode Combinations**
   ```python
   # Full anti-detection setup
   await crawler.arun(
       magic=True,
       headless=False,
       simulate_user=True,
       override_navigator=True
   )
   ```

2. **Dynamic Content Handling**
   ```python
   # Handle lazy-loaded content
   await crawler.arun(
       js_code="window.scrollTo(0, document.body.scrollHeight);",
       wait_for="css:.lazy-content",
       delay_before_return_html=2.0
   )
   ```

3. **Content Extraction Pipeline**
   ```python
   # Complete extraction setup
   await crawler.arun(
       css_selector=".main-content",
       word_count_threshold=20,
       extraction_strategy=my_strategy,
       chunking_strategy=my_chunking,
       process_iframes=True,
       remove_overlay_elements=True
   )
   ```

## Best Practices

1. **Performance Optimization**
   ```python
   await crawler.arun(
       bypass_cache=False,           # Use cache when possible
       word_count_threshold=10,      # Filter out noise
       process_iframes=False         # Skip iframes if not needed
   )
   ```

2. **Reliable Scraping**
   ```python
   await crawler.arun(
       magic=True,                   # Enable anti-detection
       delay_before_return_html=1.0, # Wait for dynamic content
       page_timeout=60000           # Longer timeout for slow pages
   )
   ```

3. **Clean Content**
   ```python
   await crawler.arun(
       remove_overlay_elements=True,  # Remove popups
       excluded_tags=['nav', 'aside'],# Remove unnecessary elements
       keep_data_attributes=False     # Remove data attributes
   )
   ```


# Extraction & Chunking Strategies API

This documentation covers the API reference for extraction and chunking strategies in Crawl4AI.

## Extraction Strategies

All extraction strategies inherit from the base `ExtractionStrategy` class and implement two key methods:
- `extract(url: str, html: str) -> List[Dict[str, Any]]`
- `run(url: str, sections: List[str]) -> List[Dict[str, Any]]`

### LLMExtractionStrategy

Used for extracting structured data using Language Models.

```python
LLMExtractionStrategy(
    # Required Parameters
    provider: str = DEFAULT_PROVIDER,     # LLM provider (e.g., "ollama/llama2")
    api_token: Optional[str] = None,      # API token
    
    # Extraction Configuration
    instruction: str = None,              # Custom extraction instruction
    schema: Dict = None,                  # Pydantic model schema for structured data
    extraction_type: str = "block",       # "block" or "schema"
    
    # Chunking Parameters
    chunk_token_threshold: int = 4000,    # Maximum tokens per chunk
    overlap_rate: float = 0.1,           # Overlap between chunks
    word_token_rate: float = 0.75,       # Word to token conversion rate
    apply_chunking: bool = True,         # Enable/disable chunking
    
    # API Configuration
    base_url: str = None,                # Base URL for API
    extra_args: Dict = {},               # Additional provider arguments
    verbose: bool = False                # Enable verbose logging
)
```

### CosineStrategy

Used for content similarity-based extraction and clustering.

```python
CosineStrategy(
    # Content Filtering
    semantic_filter: str = None,        # Topic/keyword filter
    word_count_threshold: int = 10,     # Minimum words per cluster
    sim_threshold: float = 0.3,         # Similarity threshold
    
    # Clustering Parameters
    max_dist: float = 0.2,             # Maximum cluster distance
    linkage_method: str = 'ward',       # Clustering method
    top_k: int = 3,                    # Top clusters to return
    
    # Model Configuration
    model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',  # Embedding model
    
    verbose: bool = False              # Enable verbose logging
)
```

### JsonCssExtractionStrategy

Used for CSS selector-based structured data extraction.

```python
JsonCssExtractionStrategy(
    schema: Dict[str, Any],    # Extraction schema
    verbose: bool = False      # Enable verbose logging
)

# Schema Structure
schema = {
    "name": str,              # Schema name
    "baseSelector": str,      # Base CSS selector
    "fields": [               # List of fields to extract
        {
            "name": str,      # Field name
            "selector": str,  # CSS selector
            "type": str,     # Field type: "text", "attribute", "html", "regex"
            "attribute": str, # For type="attribute"
            "pattern": str,  # For type="regex"
            "transform": str, # Optional: "lowercase", "uppercase", "strip"
            "default": Any    # Default value if extraction fails
        }
    ]
}
```

## Chunking Strategies

All chunking strategies inherit from `ChunkingStrategy` and implement the `chunk(text: str) -> list` method.

### RegexChunking

Splits text based on regex patterns.

```python
RegexChunking(
    patterns: List[str] = None  # Regex patterns for splitting
                               # Default: [r'\n\n']
)
```

### SlidingWindowChunking

Creates overlapping chunks with a sliding window approach.

```python
SlidingWindowChunking(
    window_size: int = 100,    # Window size in words
    step: int = 50             # Step size between windows
)
```

### OverlappingWindowChunking

Creates chunks with specified overlap.

```python
OverlappingWindowChunking(
    window_size: int = 1000,   # Chunk size in words
    overlap: int = 100         # Overlap size in words
)
```

## Usage Examples

### LLM Extraction

```python
from pydantic import BaseModel
from crawl4ai.extraction_strategy import LLMExtractionStrategy

# Define schema
class Article(BaseModel):
    title: str
    content: str
    author: str

# Create strategy
strategy = LLMExtractionStrategy(
    provider="ollama/llama2",
    schema=Article.schema(),
    instruction="Extract article details"
)

# Use with crawler
result = await crawler.arun(
    url="https://example.com/article",
    extraction_strategy=strategy
)

# Access extracted data
data = json.loads(result.extracted_content)
```

### CSS Extraction

```python
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

# Define schema
schema = {
    "name": "Product List",
    "baseSelector": ".product-card",
    "fields": [
        {
            "name": "title",
            "selector": "h2.title",
            "type": "text"
        },
        {
            "name": "price",
            "selector": ".price",
            "type": "text",
            "transform": "strip"
        },
        {
            "name": "image",
            "selector": "img",
            "type": "attribute",
            "attribute": "src"
        }
    ]
}

# Create and use strategy
strategy = JsonCssExtractionStrategy(schema)
result = await crawler.arun(
    url="https://example.com/products",
    extraction_strategy=strategy
)
```

### Content Chunking

```python
from crawl4ai.chunking_strategy import OverlappingWindowChunking

# Create chunking strategy
chunker = OverlappingWindowChunking(
    window_size=500,  # 500 words per chunk
    overlap=50        # 50 words overlap
)

# Use with extraction strategy
strategy = LLMExtractionStrategy(
    provider="ollama/llama2",
    chunking_strategy=chunker
)

result = await crawler.arun(
    url="https://example.com/long-article",
    extraction_strategy=strategy
)
```

## Best Practices

1. **Choose the Right Strategy**
   - Use `LLMExtractionStrategy` for complex, unstructured content
   - Use `JsonCssExtractionStrategy` for well-structured HTML
   - Use `CosineStrategy` for content similarity and clustering

2. **Optimize Chunking**
   ```python
   # For long documents
   strategy = LLMExtractionStrategy(
       chunk_token_threshold=2000,  # Smaller chunks
       overlap_rate=0.1           # 10% overlap
   )
   ```

3. **Handle Errors**
   ```python
   try:
       result = await crawler.arun(
           url="https://example.com",
           extraction_strategy=strategy
       )
       if result.success:
           content = json.loads(result.extracted_content)
   except Exception as e:
       print(f"Extraction failed: {e}")
   ```

4. **Monitor Performance**
   ```python
   strategy = CosineStrategy(
       verbose=True,  # Enable logging
       word_count_threshold=20,  # Filter short content
       top_k=5  # Limit results
   )
   ```