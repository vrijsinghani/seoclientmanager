import requests
import mimetypes
import urllib.parse
import re
from django.core.cache import cache
import logging
import tiktoken
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatLiteLLM
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import CallbackManager
import openai
from langchain.schema import HumanMessage
import markdown
from bs4 import BeautifulSoup


class TokenCounterCallback(BaseCallbackHandler):
    def __init__(self, tokenizer):
        self.llm = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.tokenizer = tokenizer

    def on_llm_start(self, serialized, prompts, **kwargs):
        for prompt in prompts:
            self.input_tokens += len(self.tokenizer.encode(prompt, disallowed_special=()))

    def on_llm_end(self, response, **kwargs):
        for generation in response.generations:
            for result in generation:
                self.output_tokens += len(self.tokenizer.encode(result.text, disallowed_special=()))

def get_models():
    data=""
    #data = cache.get('models')
    if not data:
        url = f'{settings.API_BASE_URL}/models'
        headers = {'accept': 'application/json', 'Authorization': f'Bearer {settings.LITELLM_MASTER_KEY}'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()['data']
            # Sort the data by 'id' in ascending order
            data.sort(key=lambda x: x['id'])
            cache.set('models', data, 60*60)  # Cache data for 1 hour
        else:
            return None
    return [item['id'] for item in data]

def get_llm(model_name:str, temperature=0.0):

    tokenizer=tiktoken.get_encoding("cl100k_base")
    token_counter_callback = TokenCounterCallback(tokenizer)
     
    callback_manager = CallbackManager([token_counter_callback])  

    llm = ChatOpenAI(model=model_name, 
                     base_url=settings.API_BASE_URL, 
                     api_key=settings.LITELLM_MASTER_KEY, 
                     temperature=temperature, 
                     callbacks=callback_manager)

    token_counter_callback.llm = llm
    return llm, token_counter_callback

def get_llm_openai(model_name: str, temperature=0.0) -> tuple[openai.OpenAI, BaseCallbackHandler]:
    """Creates an OpenAI chat client using the LiteLLM proxy."""

    tokenizer = tiktoken.get_encoding("cl100k_base")
    token_counter_callback = TokenCounterCallback(tokenizer)

    callback_manager = CallbackManager([token_counter_callback])  

    llm = openai.OpenAI(
        model=model_name,
        base_url=settings.OPENAI_API_BASE,
        api_key=settings.LITELLM_MASTER_KEY,
        temperature=temperature,
        callbacks=[token_counter_callback],
    )
    token_counter_callback.llm = llm

    return llm, token_counter_callback

def is_pdf_url(url: str) -> bool:
    """Determine if the given URL points to a PDF document."""
    try:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.path.endswith('.pdf'):
            return True
        response = requests.head(url, allow_redirects=True, timeout=5)
        content_type = response.headers.get('Content-Type')
        if content_type and content_type.startswith('application/pdf'):
            return True
        mime_type, _ = mimetypes.guess_type(url)
        if mime_type and mime_type.startswith('application/pdf'):
            return True
        response = requests.get(url, stream=True, timeout=5)
        return response.raw.read(1024).startswith(b'%PDF-')
    except requests.exceptions.RequestException:
        return False

def is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

def is_stock_symbol(query):
    url = f'https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={query}&apikey={settings.ALPHA_VANTAGE_API_KEY}'
    r=requests.get(url)
    data = r.json()
    print(data)
    if 'bestMatches' in data and len(data['bestMatches']) > 0:
        return True
    else:
        return False

def tokenize(text: str, tokenizer = "cl100k_base") -> int:
    """ Helper function to tokenize text and return token count """
    #logging.info(f'tokenize text: {text[:50]}...')
    return len(tokenizer.encode(text, disallowed_special=()))

def extract_top_level_domain(url):
  """Extracts only the top-level domain (TLD) from a URL, handling various cases.

  Args:
    url: The URL to extract the TLD from.

  Returns:
    The top-level domain (TLD) as a string (without protocol or subdomains), 
    or None if the TLD cannot be determined or if None is passed in.
  """
  if url is None:
    return None  # Handle None input explicitly

  try:
    # Remove protocol (http://, https://)
    url = url.split("//")[-1]  
    # Remove trailing slash
    url = url.rstrip("/")
    # Split into parts and extract TLD using the previous logic
    url_parts = url.split(".")
    if len(url_parts) > 1 and url_parts[-1] in {"com", "org", "net", "edu", "gov", "mil"}:
      return url_parts[-2]  # Return TLD (e.g., sld.com, sld.org)
    elif len(url_parts) > 2 and url_parts[-3] in {"co", "ac"}:
      return ".".join(url_parts[-2:])  # Handle "sld.co.uk", etc.
    else:
      return url_parts[-1]  # Default to last part 
  except IndexError:
    return None 

def normalize_url(url):
    """Normalize a single URL"""
    url = url.lower()
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.port == 80 and parsed_url.scheme == 'http':
        parsed_url = parsed_url._replace(netloc=parsed_url.netloc.split(':')[0])
    url = urllib.parse.urlunparse(parsed_url)
    url = url.rstrip('/')
    url = urllib.parse.urldefrag(url)[0]
    url = urllib.parse.unquote(url)
    return url

def compare_urls(url1, url2):
    """Compare two URLs after normalizing them"""
    url1 = normalize_url(url1)
    url2 = normalize_url(url2)
    return url1 == url2

def format_message(content):
    if not content:
        return ''
    
    # Process ANSI color codes
    color_map = {
        '\x1b[1m': '<strong>',
        '\x1b[0m': '</strong>',
        '\x1b[93m': '<span class="text-warning">',  # Yellow
        '\x1b[92m': '<span class="text-success">',  # Green
        '\x1b[95m': '<span class="text-info">',     # Light Blue (for magenta)
        '\x1b[91m': '<span class="text-danger">',   # Red
        '\x1b[94m': '<span class="text-primary">',  # Blue
    }

    # Replace color codes with Bootstrap classes
    for code, html in color_map.items():
        content = content.replace(code, html)

    # Remove any remaining ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content = ansi_escape.sub('', content)

    # Convert Markdown to HTML
    html_content = markdown.markdown(content, extensions=['fenced_code', 'codehilite'])

    # Parse the HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Add Bootstrap classes to elements
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        tag['class'] = tag.get('class', []) + ['mt-3', 'mb-2']
    
    for tag in soup.find_all('p'):
        tag['class'] = tag.get('class', []) + ['mb-2']
    
    for tag in soup.find_all('ul', 'ol'):
        tag['class'] = tag.get('class', []) + ['pl-4']
    
    for tag in soup.find_all('code'):
        tag['class'] = tag.get('class', []) + ['bg-light', 'p-1', 'rounded']

    # Convert back to string
    formatted_content = str(soup)

    # Ensure all spans are closed
    open_spans = formatted_content.count('<span')
    close_spans = formatted_content.count('</span>')
    if open_spans > close_spans:
        formatted_content += '</span>' * (open_spans - close_spans)

    return formatted_content
