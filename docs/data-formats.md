# Data Formats Design

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-07-03 | Initial data formats design with comprehensive input/output handling |

## Overview

This document details the comprehensive input and output format handling for the Crawler system, leveraging all crawl4ai capabilities. The system supports various input sources and output formats to accommodate different use cases and integration requirements.

## Groundtruth References

This design is based on the following groundtruth specifications:
- **Crawl4AI Context**: `groundtruth/crawl4ai_context.md` (Generated: 2025-06-16T09:14:43.423Z, Version: 0.6.3)
- **Firecrawl API Specification**: `groundtruth/firecrawl-openapi.json` (OpenAPI 3.0, Version: v1)

*Note: Data formats must be compatible with both crawl4ai capabilities and Firecrawl API requirements. When groundtruth files are updated, data format handling must be reviewed and adjusted accordingly.*

## Input Formats

### 1. URL Input Types

#### Standard HTTP/HTTPS URLs
```python
# Examples
urls = [
    "https://example.com",
    "http://example.com",
    "https://example.com/path?query=value",
    "https://subdomain.example.com",
    "https://example.com:8080/path"
]
```

#### File URLs
```python
# Local file paths
file_urls = [
    "file:///absolute/path/to/file.html",
    "file://./relative/path/to/file.html",
    "file:///C:/Windows/path/file.html"  # Windows paths
]
```

#### Raw HTML Content
```python
# Raw HTML strings
raw_html = [
    "raw:<html><head><title>Test</title></head><body>Content</body></html>",
    "raw:<!DOCTYPE html><html>...</html>",
    "raw:<div>Partial HTML content</div>"
]
```

### 2. Input Configuration Formats

#### YAML Configuration
```yaml
# config.yaml
scrape:
  timeout: 30
  headless: true
  user_agent: "Crawler/1.0"
  extraction:
    strategy: "css"
    selectors:
      title: "h1"
      content: ".main-content"
      links: "a[href]"

crawl:
  max_depth: 3
  max_pages: 100
  delay: 1.0
  patterns:
    include: [".*blog.*", ".*news.*"]
    exclude: [".*admin.*", ".*login.*"]
```

#### JSON Configuration
```json
{
  "scrape": {
    "timeout": 30,
    "headless": true,
    "user_agent": "Crawler/1.0",
    "extraction": {
      "strategy": "llm",
      "model": "openai/gpt-4o-mini",
      "prompt": "Extract main content and metadata",
      "schema": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "content": {"type": "string"},
          "author": {"type": "string"}
        }
      }
    }
  }
}
```

#### Environment Variables
```bash
# Browser configuration
CRAWLER_TIMEOUT=30
CRAWLER_HEADLESS=true
CRAWLER_USER_AGENT="Crawler/1.0"

# Proxy configuration
CRAWLER_PROXY_URL="http://proxy.example.com:8080"
CRAWLER_PROXY_USERNAME="username"
CRAWLER_PROXY_PASSWORD="password"

# LLM configuration
OPENAI_API_KEY="your-api-key"
ANTHROPIC_API_KEY="your-anthropic-key"

# Storage configuration
CRAWLER_CACHE_DIR="/path/to/cache"
CRAWLER_RESULTS_DIR="/path/to/results"
```

### 3. Batch Input Formats

#### Plain Text File
```text
# urls.txt
https://example.com
https://example.com/page1
https://example.com/page2
https://example.com/page3
```

#### CSV File
```csv
# urls.csv
url,priority,category,custom_timeout
https://example.com,high,homepage,60
https://example.com/blog,medium,blog,30
https://example.com/about,low,static,30
```

#### JSON Array
```json
[
  {
    "url": "https://example.com",
    "config": {
      "timeout": 60,
      "extraction": {
        "strategy": "css",
        "selectors": {"title": "h1"}
      }
    }
  },
  {
    "url": "https://example.com/blog",
    "config": {
      "timeout": 30,
      "extraction": {
        "strategy": "llm",
        "prompt": "Extract blog post content"
      }
    }
  }
]
```

#### JSON Lines (NDJSON)
```jsonl
{"url": "https://example.com", "category": "homepage"}
{"url": "https://example.com/blog", "category": "blog"}
{"url": "https://example.com/about", "category": "static"}
```

## Output Formats

### 1. Content Formats

#### Markdown Format
```markdown
# Page Title

## Metadata
- URL: https://example.com
- Title: Example Page
- Timestamp: 2025-07-03T10:30:00Z
- Status: 200
- Load Time: 1.23s

## Content
Main page content converted to clean markdown format...

### Subsection
More content here...

## Links
- [Internal Link](https://example.com/internal)
- [External Link](https://external.com)

## Images
![Alt text](https://example.com/image1.jpg)
![Another image](https://example.com/image2.png)

## Tables
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |

## Code Blocks
```python
def example_function():
    return "Hello, World!"
```

## Metadata
- **Processing Time**: 1.23 seconds
- **Content Length**: 1024 characters
- **Image Count**: 2
- **Link Count**: 15
```

#### HTML Format
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Example Page</title>
    <meta name="description" content="Page description">
    <meta name="keywords" content="keyword1, keyword2">
</head>
<body>
    <header>
        <h1>Page Title</h1>
        <nav>
            <ul>
                <li><a href="/home">Home</a></li>
                <li><a href="/about">About</a></li>
            </ul>
        </nav>
    </header>
    
    <main>
        <article>
            <h2>Main Content</h2>
            <p>Article content here...</p>
        </article>
    </main>
    
    <footer>
        <p>&copy; 2025 Example Company</p>
    </footer>
</body>
</html>
```

#### Plain Text Format
```text
Example Page

Main content extracted as plain text without any markup or formatting.

This includes all text content from the page including headings, paragraphs, lists, and other text elements but without any HTML tags or markdown formatting.

Lists are converted to simple text:
- Item 1
- Item 2
- Item 3

Tables are converted to aligned text format:
Column 1    Column 2    Column 3
Data 1      Data 2      Data 3

Links are shown as: Link Text (https://example.com/link)
```

### 2. Structured Data Formats

#### JSON Format
```json
{
  "url": "https://example.com",
  "timestamp": "2025-07-03T10:30:00Z",
  "success": true,
  "metadata": {
    "title": "Example Page",
    "description": "Page description",
    "language": "en",
    "charset": "UTF-8",
    "status_code": 200,
    "final_url": "https://example.com",
    "redirects": [],
    "load_time": 1.23,
    "content_length": 15678,
    "content_type": "text/html",
    "server": "nginx/1.18.0",
    "last_modified": "2025-07-03T09:00:00Z"
  },
  "content": {
    "markdown": "# Page Title\n\nContent...",
    "html": "<html>...</html>",
    "text": "Plain text content...",
    "cleaned_html": "<div class=\"main-content\">...</div>"
  },
  "extracted_data": {
    "title": "Page Title",
    "author": "John Doe",
    "publish_date": "2025-07-03",
    "tags": ["tag1", "tag2", "tag3"],
    "custom_fields": {
      "price": "$29.99",
      "rating": "4.5/5",
      "availability": "In Stock"
    }
  },
  "links": {
    "internal": [
      {
        "url": "https://example.com/internal",
        "text": "Internal Link",
        "title": "Link Title",
        "rel": "nofollow"
      }
    ],
    "external": [
      {
        "url": "https://external.com",
        "text": "External Link",
        "title": "External Site",
        "rel": "noopener"
      }
    ]
  },
  "media": {
    "images": [
      {
        "src": "https://example.com/image1.jpg",
        "alt": "Alt text",
        "title": "Image title",
        "width": 800,
        "height": 600,
        "size": 51200,
        "format": "JPEG"
      }
    ],
    "videos": [
      {
        "src": "https://example.com/video1.mp4",
        "poster": "https://example.com/video1-thumb.jpg",
        "duration": 120,
        "format": "MP4"
      }
    ],
    "audio": [
      {
        "src": "https://example.com/audio1.mp3",
        "duration": 180,
        "format": "MP3"
      }
    ]
  },
  "tables": [
    {
      "headers": ["Column 1", "Column 2", "Column 3"],
      "rows": [
        ["Data 1", "Data 2", "Data 3"],
        ["Data 4", "Data 5", "Data 6"]
      ],
      "caption": "Table caption"
    }
  ],
  "forms": [
    {
      "action": "/submit",
      "method": "POST",
      "fields": [
        {
          "name": "username",
          "type": "text",
          "required": true
        },
        {
          "name": "password",
          "type": "password",
          "required": true
        }
      ]
    }
  ],
  "performance": {
    "load_time": 1.23,
    "dom_content_loaded": 0.89,
    "first_paint": 0.45,
    "largest_contentful_paint": 1.12,
    "cumulative_layout_shift": 0.02
  },
  "accessibility": {
    "has_alt_text": true,
    "has_headings": true,
    "has_landmarks": true,
    "color_contrast_issues": 0
  }
}
```

**Data Structure Note**: The above JSON structure represents the complete data model. The `content` field contains a nested dictionary with format-specific content:
- `content.markdown`: Extracted content in markdown format
- `content.html`: Original HTML content
- `content.text`: Plain text extraction
- `content.extracted_data`: Structured data extraction results

CLI commands should access specific content formats using defensive programming to handle cases where content might be a string instead of a dictionary structure.

#### XML Format
```xml
<?xml version="1.0" encoding="UTF-8"?>
<scrape_result>
    <url>https://example.com</url>
    <timestamp>2025-07-03T10:30:00Z</timestamp>
    <success>true</success>
    
    <metadata>
        <title>Example Page</title>
        <description>Page description</description>
        <language>en</language>
        <status_code>200</status_code>
        <load_time>1.23</load_time>
    </metadata>
    
    <content>
        <markdown><![CDATA[# Page Title

Content...]]></markdown>
        <html><![CDATA[<html>...</html>]]></html>
        <text><![CDATA[Plain text content...]]></text>
    </content>
    
    <extracted_data>
        <title>Page Title</title>
        <author>John Doe</author>
        <publish_date>2025-07-03</publish_date>
        <tags>
            <tag>tag1</tag>
            <tag>tag2</tag>
        </tags>
    </extracted_data>
    
    <links>
        <internal>
            <link>
                <url>https://example.com/internal</url>
                <text>Internal Link</text>
            </link>
        </internal>
        <external>
            <link>
                <url>https://external.com</url>
                <text>External Link</text>
            </link>
        </external>
    </links>
</scrape_result>
```

#### CSV Format
```csv
# Single row per page
url,title,timestamp,status_code,load_time,content_length,link_count,image_count
https://example.com,Example Page,2025-07-03T10:30:00Z,200,1.23,15678,25,5

# Or detailed format with extracted fields
url,title,author,publish_date,content_preview,tag1,tag2,tag3
https://example.com,Example Page,John Doe,2025-07-03,"Content preview...",tag1,tag2,tag3
```

### 3. Binary Formats

#### Screenshot (PNG/JPEG)
```python
# Base64 encoded screenshot
screenshot_data = {
    "format": "png",
    "data": "iVBORw0KGgoAAAANSUhEUgAA...",  # Base64 encoded
    "metadata": {
        "width": 1920,
        "height": 1080,
        "size": 512000,
        "timestamp": "2025-07-03T10:30:00Z"
    }
}

# Binary file
with open("screenshot.png", "wb") as f:
    f.write(base64.b64decode(screenshot_data["data"]))
```

#### PDF Format
```python
# PDF document bytes
pdf_data = {
    "format": "pdf",
    "data": bytes,  # Raw PDF bytes
    "metadata": {
        "page_count": 1,
        "size": 1024000,
        "timestamp": "2025-07-03T10:30:00Z",
        "options": {
            "format": "A4",
            "landscape": false,
            "print_background": true
        }
    }
}

# Save to file
with open("page.pdf", "wb") as f:
    f.write(pdf_data["data"])
```

### 4. Database Formats

#### SQLite Database (Primary Storage)
SQLite is the primary storage format for Phase 1 implementation, providing unified storage for all system components.

```sql
-- Core tables for unified SQLite storage
CREATE TABLE crawl_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    url TEXT NOT NULL,
    title TEXT,
    timestamp DATETIME,
    status_code INTEGER,
    success BOOLEAN DEFAULT FALSE,
    load_time REAL,
    content_markdown TEXT,
    content_html TEXT,
    content_text TEXT,
    extracted_data JSON,
    metadata JSON,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX(job_id),
    INDEX(url),
    INDEX(timestamp),
    INDEX(created_at)
);

CREATE TABLE crawl_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_result_id INTEGER,
    url TEXT,
    text TEXT,
    title TEXT,
    type TEXT, -- 'internal' or 'external'
    rel TEXT,
    FOREIGN KEY (crawl_result_id) REFERENCES crawl_results (id),
    INDEX(crawl_result_id),
    INDEX(type)
);

CREATE TABLE crawl_media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_result_id INTEGER,
    media_type TEXT, -- 'image', 'video', 'audio'
    src TEXT,
    alt TEXT,
    title TEXT,
    width INTEGER,
    height INTEGER,
    size INTEGER,
    format TEXT,
    FOREIGN KEY (crawl_result_id) REFERENCES crawl_results (id),
    INDEX(crawl_result_id),
    INDEX(media_type)
);

-- Browser sessions for crawl4ai session management
CREATE TABLE browser_sessions (
    session_id TEXT PRIMARY KEY,
    config JSON,
    state_data JSON,
    page_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    INDEX(expires_at),
    INDEX(last_accessed),
    INDEX(is_active)
);

-- Cache for performance optimization
CREATE TABLE cache_entries (
    cache_key TEXT PRIMARY KEY,
    data_value JSON,
    data_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    access_count INTEGER DEFAULT 0,
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX(expires_at),
    INDEX(access_count),
    INDEX(data_type)
);

-- Job queue for async operations
CREATE TABLE job_queue (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL, -- 'scrape', 'batch_scrape', 'crawl'
    status TEXT DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    priority INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    job_data JSON,
    result_data JSON,
    error_message TEXT,
    INDEX(status),
    INDEX(priority),
    INDEX(created_at),
    INDEX(job_type)
);
```

#### Future Database Migration Support
While SQLite is used for Phase 1, the system is designed for future migration to distributed databases when scale requirements grow:

```sql
-- Example PostgreSQL migration target (Future)
-- Same schema but with PostgreSQL-specific optimizations
-- UUID primary keys, partitioning, etc.

-- Note: Cache remains in SQLite for simplicity
-- Future PostgreSQL can handle caching with optimized indexes
```

## Format Conversion

### 1. Content Format Conversion

#### Markdown to HTML
```python
import markdown

def markdown_to_html(markdown_content: str) -> str:
    """Convert markdown to HTML."""
    return markdown.markdown(
        markdown_content,
        extensions=['tables', 'fenced_code', 'toc']
    )
```

#### HTML to Text
```python
from bs4 import BeautifulSoup

def html_to_text(html_content: str) -> str:
    """Convert HTML to plain text."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Get text and clean up
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    
    return text
```

#### JSON to CSV
```python
import csv
import json
from typing import List, Dict

def json_to_csv(json_data: List[Dict], output_file: str, fields: List[str] = None):
    """Convert JSON array to CSV."""
    if not json_data:
        return
    
    if fields is None:
        fields = list(json_data[0].keys())
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        
        for row in json_data:
            # Flatten nested objects
            flattened_row = {}
            for field in fields:
                value = row.get(field, '')
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                flattened_row[field] = value
            writer.writerow(flattened_row)
```

### 2. Data Structure Conversion

#### Crawl4ai to Internal Format
```python
from crawl4ai import CrawlResult

def convert_crawl4ai_result(crawl_result: CrawlResult) -> dict:
    """Convert crawl4ai CrawlResult to internal format."""
    return {
        "success": crawl_result.success,
        "url": crawl_result.url,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": {
            "title": getattr(crawl_result, 'title', ''),
            "status_code": getattr(crawl_result, 'status_code', 0),
            "load_time": getattr(crawl_result, 'load_time', 0),
            "content_length": len(crawl_result.markdown.raw_markdown) if crawl_result.markdown else 0
        },
        "content": {
            "markdown": crawl_result.markdown.fit_markdown if crawl_result.markdown else '',
            "html": crawl_result.cleaned_html or '',
            "text": crawl_result.text or ''
        },
        "extracted_data": json.loads(crawl_result.extracted_content) if crawl_result.extracted_content else {},
        "links": {
            "internal": [{"url": link.href, "text": link.text} for link in crawl_result.links.internal] if crawl_result.links else [],
            "external": [{"url": link.href, "text": link.text} for link in crawl_result.links.external] if crawl_result.links else []
        },
        "media": {
            "images": [{"src": img.src, "alt": img.alt} for img in crawl_result.media.images] if crawl_result.media else [],
            "videos": [{"src": vid.src} for vid in crawl_result.media.videos] if crawl_result.media else []
        },
        "screenshot": crawl_result.screenshot,
        "pdf": crawl_result.pdf.hex() if crawl_result.pdf else None,
        "error_message": crawl_result.error_message
    }
```

#### Internal to Firecrawl Format
```python
def convert_to_firecrawl_format(internal_result: dict) -> dict:
    """Convert internal format to Firecrawl-compatible format."""
    return {
        "markdown": internal_result["content"]["markdown"],
        "html": internal_result["content"]["html"],
        "rawHtml": internal_result["content"]["html"],  # Same as html for compatibility
        "links": [link["url"] for link in internal_result["links"]["internal"] + internal_result["links"]["external"]],
        "screenshot": internal_result["screenshot"],
        "metadata": {
            "title": internal_result["metadata"]["title"],
            "description": internal_result["metadata"].get("description", ""),
            "language": internal_result["metadata"].get("language", "en"),
            "sourceURL": internal_result["url"],
            "statusCode": internal_result["metadata"]["status_code"],
            "error": internal_result["error_message"]
        },
        "llm_extraction": internal_result["extracted_data"]
    }
```

## Template System

### 1. Output Templates

#### Markdown Template
```jinja2
{# markdown_template.md.j2 #}
# {{ title }}

**URL**: {{ url }}  
**Timestamp**: {{ timestamp }}  
**Status**: {{ status_code }}  

## Content
{{ content.markdown }}

{% if extracted_data %}
## Extracted Data
{% for key, value in extracted_data.items() %}
- **{{ key.title() }}**: {{ value }}
{% endfor %}
{% endif %}

{% if links.internal %}
## Internal Links
{% for link in links.internal %}
- [{{ link.text }}]({{ link.url }})
{% endfor %}
{% endif %}

{% if links.external %}
## External Links
{% for link in links.external %}
- [{{ link.text }}]({{ link.url }})
{% endfor %}
{% endif %}

{% if media.images %}
## Images
{% for image in media.images %}
![{{ image.alt }}]({{ image.src }})
{% endfor %}
{% endif %}

---
*Crawled on {{ timestamp }} | Load time: {{ metadata.load_time }}s*
```

#### HTML Template
```html
<!-- html_template.html.j2 -->
<!DOCTYPE html>
<html lang="{{ metadata.language|default('en') }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Crawl Result</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .metadata { background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .content { line-height: 1.6; }
        .links { margin-top: 20px; }
        .links ul { list-style-type: none; padding: 0; }
        .links li { margin: 5px 0; }
        .footer { border-top: 1px solid #ddd; margin-top: 30px; padding-top: 15px; color: #666; }
    </style>
</head>
<body>
    <div class="metadata">
        <h1>{{ title }}</h1>
        <p><strong>URL:</strong> <a href="{{ url }}">{{ url }}</a></p>
        <p><strong>Crawled:</strong> {{ timestamp }}</p>
        <p><strong>Status:</strong> {{ status_code }}</p>
        <p><strong>Load Time:</strong> {{ metadata.load_time }}s</p>
    </div>

    <div class="content">
        {{ content.html|safe }}
    </div>

    {% if extracted_data %}
    <div class="extracted-data">
        <h2>Extracted Data</h2>
        <ul>
        {% for key, value in extracted_data.items() %}
            <li><strong>{{ key.title() }}:</strong> {{ value }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}

    {% if links.internal or links.external %}
    <div class="links">
        {% if links.internal %}
        <h3>Internal Links</h3>
        <ul>
        {% for link in links.internal %}
            <li><a href="{{ link.url }}">{{ link.text }}</a></li>
        {% endfor %}
        </ul>
        {% endif %}

        {% if links.external %}
        <h3>External Links</h3>
        <ul>
        {% for link in links.external %}
            <li><a href="{{ link.url }}" target="_blank">{{ link.text }}</a></li>
        {% endfor %}
        </ul>
        {% endif %}
    </div>
    {% endif %}

    <div class="footer">
        <p>Generated by Crawler System on {{ timestamp }}</p>
    </div>
</body>
</html>
```

### 2. Custom Templates

#### Configuration
```yaml
# template_config.yaml
templates:
  markdown:
    default: "templates/markdown_default.md.j2"
    news: "templates/markdown_news.md.j2"
    ecommerce: "templates/markdown_ecommerce.md.j2"
  
  html:
    default: "templates/html_default.html.j2"
    report: "templates/html_report.html.j2"
  
  json:
    default: "templates/json_default.json.j2"
    structured: "templates/json_structured.json.j2"
```

#### Template Engine
```python
from jinja2 import Environment, FileSystemLoader

class TemplateEngine:
    """Template engine for formatting output."""
    
    def __init__(self, template_dir: str = "templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))
    
    def render(self, template_name: str, data: dict) -> str:
        """Render template with data."""
        template = self.env.get_template(template_name)
        return template.render(**data)
    
    def render_string(self, template_string: str, data: dict) -> str:
        """Render template string with data."""
        template = self.env.from_string(template_string)
        return template.render(**data)
```

## Data Validation

### 1. Input Validation

#### URL Validation
```python
import re
from urllib.parse import urlparse

def validate_url(url: str) -> bool:
    """Validate URL format."""
    if not url:
        return False
    
    # Handle special formats
    if url.startswith('raw:'):
        return len(url) > 4  # Must have content after 'raw:'
    
    if url.startswith('file://'):
        return True  # Basic file URL check
    
    # Standard URL validation
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except:
        return False
```

#### Configuration Validation
```python
from pydantic import BaseModel, validator
from typing import Optional, List, Dict

class ScrapeConfig(BaseModel):
    """Validation model for scrape configuration."""
    url: str
    timeout: Optional[int] = 30
    headless: Optional[bool] = True
    user_agent: Optional[str] = None
    formats: Optional[List[str]] = ["markdown"]
    
    @validator('url')
    def validate_url(cls, v):
        if not validate_url(v):
            raise ValueError('Invalid URL format')
        return v
    
    @validator('timeout')
    def validate_timeout(cls, v):
        if v <= 0 or v > 300:
            raise ValueError('Timeout must be between 1 and 300 seconds')
        return v
    
    @validator('formats')
    def validate_formats(cls, v):
        valid_formats = ['markdown', 'html', 'text', 'json', 'csv', 'xml']
        for fmt in v:
            if fmt not in valid_formats:
                raise ValueError(f'Invalid format: {fmt}')
        return v
```

### 2. Output Validation

#### Schema Validation
```python
from jsonschema import validate, ValidationError

# JSON Schema for output validation
output_schema = {
    "type": "object",
    "required": ["url", "success", "timestamp"],
    "properties": {
        "url": {"type": "string", "format": "uri"},
        "success": {"type": "boolean"},
        "timestamp": {"type": "string", "format": "date-time"},
        "metadata": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "status_code": {"type": "integer", "minimum": 100, "maximum": 599}
            }
        },
        "content": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "html": {"type": "string"},
                "text": {"type": "string"}
            }
        }
    }
}

def validate_output(data: dict) -> bool:
    """Validate output data against schema."""
    try:
        validate(instance=data, schema=output_schema)
        return True
    except ValidationError:
        return False
```

## Performance Optimization

### 1. Format-Specific Optimizations

#### Lazy Loading
```python
class LazyContent:
    """Lazy loading for large content."""
    
    def __init__(self, loader_func):
        self._loader = loader_func
        self._loaded = False
        self._content = None
    
    def __getattr__(self, name):
        if not self._loaded:
            self._content = self._loader()
            self._loaded = True
        return getattr(self._content, name)
```

#### Streaming Output
```python
import json
from typing import Iterator

def stream_json_results(results: Iterator[dict]) -> Iterator[str]:
    """Stream JSON results one by one."""
    yield "["
    first = True
    for result in results:
        if not first:
            yield ","
        yield json.dumps(result)
        first = False
    yield "]"
```

#### Compression
```python
import gzip
import json

def compress_json(data: dict) -> bytes:
    """Compress JSON data."""
    json_str = json.dumps(data)
    return gzip.compress(json_str.encode('utf-8'))

def decompress_json(compressed_data: bytes) -> dict:
    """Decompress JSON data."""
    json_str = gzip.decompress(compressed_data).decode('utf-8')
    return json.loads(json_str)
```

### 2. Memory Management

#### Chunked Processing
```python
def process_large_dataset(data_iterator, chunk_size: int = 1000):
    """Process large datasets in chunks."""
    chunk = []
    for item in data_iterator:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    
    if chunk:  # Process remaining items
        yield chunk
```

#### Memory-Mapped Files
```python
import mmap

def read_large_file_mmap(filename: str):
    """Read large files using memory mapping."""
    with open(filename, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
            # Process file content without loading all into memory
            for line in iter(mmapped_file.readline, b""):
                yield line.decode('utf-8').strip()
```

## Integration Examples

### 1. Data Pipeline Integration

#### Apache Airflow DAG
```python
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta

def crawl_and_process(**context):
    """Crawl data and process results."""
    # Crawl data
    results = crawler.crawl(
        url="https://example.com",
        output_format="json"
    )
    
    # Process and transform
    processed_data = transform_data(results)
    
    # Store in database
    store_in_database(processed_data)

dag = DAG(
    'web_crawling_pipeline',
    default_args={
        'owner': 'data-team',
        'depends_on_past': False,
        'start_date': datetime(2025, 7, 3),
        'retries': 1,
        'retry_delay': timedelta(minutes=5)
    },
    schedule_interval=timedelta(hours=6),
    catchup=False
)

crawl_task = PythonOperator(
    task_id='crawl_and_process',
    python_callable=crawl_and_process,
    dag=dag
)
```

#### Apache Kafka Integration
```python
from kafka import KafkaProducer
import json

class CrawlResultProducer:
    """Kafka producer for crawl results."""
    
    def __init__(self, bootstrap_servers: List[str]):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    
    def send_result(self, topic: str, result: dict):
        """Send crawl result to Kafka topic."""
        self.producer.send(topic, result)
        self.producer.flush()
```

### 2. Database Integration

#### SQLAlchemy Models
```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CrawlResult(Base):
    """SQLAlchemy model for crawl results."""
    __tablename__ = 'crawl_results'
    
    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    title = Column(String(512))
    success = Column(Boolean, default=False)
    status_code = Column(Integer)
    timestamp = Column(DateTime)
    content_markdown = Column(Text)
    content_html = Column(Text)
    content_text = Column(Text)
    extracted_data = Column(JSON)
    metadata = Column(JSON)
    error_message = Column(Text)
```

#### Elasticsearch Integration
```python
from elasticsearch import Elasticsearch

class CrawlResultIndexer:
    """Elasticsearch indexer for crawl results."""
    
    def __init__(self, host: str = "localhost", port: int = 9200):
        self.es = Elasticsearch([{"host": host, "port": port}])
    
    def index_result(self, result: dict, index: str = "crawl_results"):
        """Index crawl result in Elasticsearch."""
        doc = {
            "url": result["url"],
            "title": result["metadata"]["title"],
            "content": result["content"]["text"],
            "extracted_data": result["extracted_data"],
            "timestamp": result["timestamp"],
            "metadata": result["metadata"]
        }
        
        self.es.index(index=index, body=doc)
    
    def search(self, query: str, index: str = "crawl_results"):
        """Search indexed results."""
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^2", "content", "extracted_data.*"]
                }
            }
        }
        
        return self.es.search(index=index, body=search_body)
```

## Future Enhancements

### Planned Features
1. **Real-time Streaming**: Support for real-time data streaming
2. **Binary Formats**: Support for additional binary formats (DOCX, XLSX)
3. **Advanced Compression**: Advanced compression algorithms
4. **Schema Evolution**: Support for schema versioning and evolution
5. **Multi-format Output**: Single operation producing multiple formats

### Extensibility Points
1. **Custom Formats**: Plugin system for custom output formats
2. **Custom Templates**: User-defined template system
3. **Custom Validators**: Custom validation rules
4. **Format Converters**: Custom format conversion plugins
5. **Storage Backends**: Custom storage backend integrations