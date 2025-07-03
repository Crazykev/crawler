# Firecrawl-Compatible API Design

## Overview

The Firecrawl-compatible API layer provides 100% compatibility with the Firecrawl API specification, allowing existing Firecrawl users to migrate seamlessly to our system. This layer acts as an adapter between the Firecrawl API format and our internal crawler system.

**Important**: This Firecrawl-compatible API has **HIGHEST PRIORITY** for implementation. All development resources should focus on achieving full Firecrawl compatibility before implementing the Native API.

## Groundtruth References

This design is directly based on the official Firecrawl API specification:
- **Firecrawl OpenAPI Specification**: `groundtruth/firecrawl-openapi.json` (OpenAPI 3.0, Version: v1)
- **Crawl4AI Context**: `groundtruth/crawl4ai_context.md` (Generated: 2025-06-16T09:14:43.423Z, Version: 0.6.3)

*Note: This implementation must maintain 100% compatibility with the Firecrawl API specification. When groundtruth files are updated, this implementation must be reviewed and adjusted accordingly.*

## Base URL and Versioning

```
Base URL: https://api.crawler.example.com
Firecrawl Compatibility Path: /
Compatible Version: v1
Full Base URL: https://api.crawler.example.com/v1
```

## Authentication

### Bearer Token Authentication
```http
Authorization: Bearer your_api_key_here
```

## Endpoint Mapping

Our system provides exact endpoint compatibility with Firecrawl:

```
Firecrawl Endpoints          → Our Internal Services
/scrape                      → ScrapeService.scrape_single()
/batch/scrape               → ScrapeService.scrape_batch()
/batch/scrape/{id}          → JobManager.get_job_status()
/batch/scrape/{id}/errors   → JobManager.get_job_errors()
/crawl                      → CrawlService.start_crawl()
/crawl/active               → CrawlService.list_active_crawls()
/crawl/{id}                 → CrawlService.get_crawl_status()
/crawl/{id}/errors          → CrawlService.get_crawl_errors()
/extract                    → ScrapeService.extract_content()
```

## Scraping Endpoints

### POST /scrape
Scrape a single URL and get the result immediately.

**Request Body (Firecrawl Compatible):**
```json
{
  "url": "https://example.com",
  "formats": ["markdown", "html", "links", "screenshot"],
  "onlyMainContent": true,
  "includeTags": ["h1", "h2", "p", "a"],
  "excludeTags": ["script", "style", "nav"],
  "headers": {
    "User-Agent": "Custom Bot 1.0"
  },
  "waitFor": 5000,
  "mobile": false,
  "skipTlsVerification": false,
  "timeout": 30000,
  "parsePDF": true,
  "actions": [
    {
      "type": "wait",
      "milliseconds": 2000,
      "selector": "#content"
    },
    {
      "type": "click",
      "selector": ".load-more"
    },
    {
      "type": "screenshot",
      "fullPage": true
    }
  ],
  "location": {
    "country": "US",
    "languages": ["en-US"]
  },
  "removeBase64Images": true,
  "blockAds": true,
  "proxy": "basic",
  "storeInCache": true,
  "jsonOptions": {
    "schema": {
      "type": "object",
      "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"}
      }
    },
    "systemPrompt": "Extract the main content",
    "prompt": "Get the title and main content"
  }
}
```

**Response (Firecrawl Compatible):**
```json
{
  "success": true,
  "data": {
    "markdown": "# Page Title\n\nMain content here...",
    "html": "<html><head><title>Page Title</title></head><body>...</body></html>",
    "rawHtml": "<html>...</html>",
    "links": [
      "https://example.com/link1",
      "https://example.com/link2"
    ],
    "screenshot": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "metadata": {
      "title": "Page Title",
      "description": "Page description",
      "language": "en",
      "sourceURL": "https://example.com",
      "statusCode": 200,
      "error": null
    },
    "llm_extraction": {
      "title": "Extracted Title",
      "content": "Extracted content"
    }
  }
}
```

### POST /batch/scrape
Initiate a batch scrape of multiple URLs.

**Request Body (Firecrawl Compatible):**
```json
{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3"
  ],
  "webhook": {
    "url": "https://your-webhook.com/callback",
    "headers": {
      "Authorization": "Bearer token"
    },
    "metadata": {
      "job_name": "batch_scrape_001"
    },
    "events": ["completed"]
  },
  "maxConcurrency": 5,
  "ignoreInvalidURLs": false,
  "onlyMainContent": true,
  "includeTags": ["h1", "h2", "p"],
  "excludeTags": ["script", "style"],
  "maxAge": 0,
  "headers": {
    "User-Agent": "Custom Bot 1.0"
  },
  "waitFor": 0,
  "mobile": false,
  "skipTlsVerification": false,
  "timeout": 30000,
  "parsePDF": true,
  "jsonOptions": {
    "schema": {
      "type": "object",
      "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"}
      }
    },
    "systemPrompt": "Extract title and summary",
    "prompt": "Get the main title and a brief summary"
  },
  "actions": [
    {
      "type": "wait",
      "milliseconds": 2000,
      "selector": ".content"
    }
  ],
  "location": {
    "country": "US",
    "languages": ["en-US"]
  },
  "removeBase64Images": true,
  "blockAds": true,
  "proxy": "basic",
  "storeInCache": true,
  "formats": ["markdown", "json"],
  "zeroDataRetention": false
}
```

**Response (Firecrawl Compatible):**
```json
{
  "success": true,
  "id": "batch_12345678-1234-1234-1234-123456789012",
  "url": "https://api.crawler.example.com/v1/batch/scrape/batch_12345678-1234-1234-1234-123456789012",
  "invalidURLs": []
}
```

### GET /batch/scrape/{id}
Check the status of a batch scrape job.

**Response (Firecrawl Compatible):**
```json
{
  "status": "completed",
  "total": 3,
  "completed": 3,
  "creditsUsed": 3,
  "expiresAt": "2025-07-03T11:30:00Z",
  "next": null,
  "data": [
    {
      "markdown": "# Page 1\n\nContent...",
      "html": "<html>...</html>",
      "rawHtml": "<html>...</html>",
      "links": ["https://example.com/link1"],
      "screenshot": null,
      "metadata": {
        "title": "Page 1",
        "description": "Description",
        "language": "en",
        "sourceURL": "https://example.com/page1",
        "statusCode": 200,
        "error": null
      },
      "llm_extraction": {
        "title": "Page 1 Title",
        "summary": "Page 1 summary"
      }
    },
    {
      "markdown": "# Page 2\n\nContent...",
      "html": "<html>...</html>",
      "rawHtml": "<html>...</html>",
      "links": ["https://example.com/link2"],
      "screenshot": null,
      "metadata": {
        "title": "Page 2",
        "description": "Description",
        "language": "en",
        "sourceURL": "https://example.com/page2",
        "statusCode": 200,
        "error": null
      },
      "llm_extraction": {
        "title": "Page 2 Title",
        "summary": "Page 2 summary"
      }
    },
    {
      "markdown": "# Page 3\n\nContent...",
      "html": "<html>...</html>",
      "rawHtml": "<html>...</html>",
      "links": ["https://example.com/link3"],
      "screenshot": null,
      "metadata": {
        "title": "Page 3",
        "description": "Description",
        "language": "en",
        "sourceURL": "https://example.com/page3",
        "statusCode": 200,
        "error": null
      },
      "llm_extraction": {
        "title": "Page 3 Title",
        "summary": "Page 3 summary"
      }
    }
  ]
}
```

### DELETE /batch/scrape/{id}
Cancel a running batch scrape job.

**Response (Firecrawl Compatible):**
```json
{
  "success": true,
  "message": "Batch scrape job cancelled successfully"
}
```

### GET /batch/scrape/{id}/errors
Retrieve any errors that occurred during a batch scrape job.

**Response (Firecrawl Compatible):**
```json
{
  "errors": [
    {
      "id": "error_001",
      "timestamp": "2025-07-03T10:32:00Z",
      "url": "https://example.com/error-page",
      "error": "Timeout after 30 seconds"
    },
    {
      "id": "error_002",
      "timestamp": "2025-07-03T10:33:00Z",
      "url": "https://example.com/not-found",
      "error": "404 Not Found"
    }
  ],
  "robotsBlocked": [
    "https://example.com/blocked-by-robots"
  ]
}
```

## Crawling Endpoints

### POST /crawl
Start a crawl from a specific URL.

**Request Body (Firecrawl Compatible):**
```json
{
  "url": "https://example.com",
  "excludePaths": ["/admin/*", "/private/*"],
  "includePaths": ["/blog/*", "/news/*"],
  "maxDepth": 3,
  "maxDiscoveryDepth": 5,
  "ignoreSitemap": false,
  "ignoreQueryParameters": true,
  "limit": 100,
  "crawlEntireDomain": false,
  "allowExternalLinks": false,
  "allowSubdomains": true,
  "delay": 1000,
  "maxConcurrency": 5,
  "webhook": {
    "url": "https://your-webhook.com/callback",
    "headers": {
      "Authorization": "Bearer token"
    },
    "metadata": {
      "crawl_name": "example_crawl"
    },
    "events": ["page_completed", "crawl_completed"]
  },
  "scrapeOptions": {
    "formats": ["markdown", "json"],
    "onlyMainContent": true,
    "includeTags": ["h1", "h2", "p", "a"],
    "excludeTags": ["script", "style", "nav"],
    "headers": {
      "User-Agent": "Crawler Bot 1.0"
    },
    "waitFor": 2000,
    "mobile": false,
    "skipTlsVerification": false,
    "timeout": 30000,
    "parsePDF": true,
    "jsonOptions": {
      "schema": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "content": {"type": "string"},
          "category": {"type": "string"}
        }
      },
      "systemPrompt": "Extract structured content",
      "prompt": "Extract title, main content, and categorize the page"
    },
    "actions": [
      {
        "type": "wait",
        "milliseconds": 2000,
        "selector": ".content-loaded"
      },
      {
        "type": "click",
        "selector": ".accept-cookies"
      }
    ],
    "location": {
      "country": "US",
      "languages": ["en-US"]
    },
    "removeBase64Images": true,
    "blockAds": true,
    "proxy": "basic",
    "storeInCache": true
  },
  "zeroDataRetention": false
}
```

**Response (Firecrawl Compatible):**
```json
{
  "success": true,
  "id": "crawl_12345678-1234-1234-1234-123456789012",
  "url": "https://api.crawler.example.com/v1/crawl/crawl_12345678-1234-1234-1234-123456789012"
}
```

### GET /crawl/active
Retrieve a list of all active crawl jobs.

**Response (Firecrawl Compatible):**
```json
{
  "success": true,
  "crawls": [
    {
      "id": "crawl_12345678-1234-1234-1234-123456789012",
      "teamId": "team_123",
      "url": "https://example.com",
      "status": "running",
      "options": {
        "scrapeOptions": {
          "formats": ["markdown", "json"],
          "onlyMainContent": true
        }
      }
    },
    {
      "id": "crawl_87654321-4321-4321-4321-210987654321",
      "teamId": "team_123",
      "url": "https://another-example.com",
      "status": "running",
      "options": {
        "scrapeOptions": {
          "formats": ["markdown"],
          "onlyMainContent": false
        }
      }
    }
  ]
}
```

### GET /crawl/{id}
Check the status of a crawl job.

**Response (Firecrawl Compatible):**
```json
{
  "status": "completed",
  "total": 25,
  "completed": 25,
  "creditsUsed": 25,
  "expiresAt": "2025-07-03T12:00:00Z",
  "next": null,
  "data": [
    {
      "markdown": "# Home Page\n\nWelcome to our website...",
      "html": "<html><head><title>Home</title></head><body>...</body></html>",
      "rawHtml": "<html>...</html>",
      "links": [
        "https://example.com/about",
        "https://example.com/services"
      ],
      "screenshot": null,
      "metadata": {
        "title": "Home - Example Company",
        "description": "Welcome to Example Company",
        "language": "en",
        "sourceURL": "https://example.com",
        "statusCode": 200,
        "error": null
      },
      "llm_extraction": {
        "title": "Home Page",
        "content": "Welcome to our website where we provide excellent services...",
        "category": "homepage"
      }
    },
    {
      "markdown": "# About Us\n\nWe are a leading company...",
      "html": "<html><head><title>About</title></head><body>...</body></html>",
      "rawHtml": "<html>...</html>",
      "links": [
        "https://example.com",
        "https://example.com/contact"
      ],
      "screenshot": null,
      "metadata": {
        "title": "About Us - Example Company",
        "description": "Learn about our company",
        "language": "en",
        "sourceURL": "https://example.com/about",
        "statusCode": 200,
        "error": null
      },
      "llm_extraction": {
        "title": "About Us",
        "content": "We are a leading company in our industry with over 20 years of experience...",
        "category": "about"
      }
    }
  ]
}
```

### DELETE /crawl/{id}
Cancel a running crawl job.

**Response (Firecrawl Compatible):**
```json
{
  "success": true,
  "message": "Crawl job cancelled successfully"
}
```

### GET /crawl/{id}/errors
Retrieve any errors that occurred during a crawl job.

**Response (Firecrawl Compatible):**
```json
{
  "errors": [
    {
      "id": "error_001",
      "timestamp": "2025-07-03T10:45:00Z",
      "url": "https://example.com/broken-page",
      "error": "404 Not Found"
    },
    {
      "id": "error_002",
      "timestamp": "2025-07-03T10:47:00Z",
      "url": "https://example.com/timeout-page",
      "error": "Timeout after 30 seconds"
    }
  ],
  "robotsBlocked": [
    "https://example.com/admin",
    "https://example.com/private"
  ]
}
```

## Extract Endpoint

### POST /extract
Extract structured data from URLs based on a prompt and/or a JSON schema.

**Request Body (Firecrawl Compatible):**
```json
{
  "urls": [
    "https://example.com/article1",
    "https://example.com/article2",
    "https://example.com/article3"
  ],
  "prompt": "Extract the article title, author, publication date, and main content",
  "schema": {
    "type": "object",
    "properties": {
      "title": {
        "type": "string",
        "description": "The main title of the article"
      },
      "author": {
        "type": "string",
        "description": "The author of the article"
      },
      "publication_date": {
        "type": "string",
        "description": "The publication date in YYYY-MM-DD format"
      },
      "content": {
        "type": "string",
        "description": "The main content of the article"
      },
      "tags": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of tags or categories for the article"
      }
    },
    "required": ["title", "content"]
  },
  "enableWebSearch": false,
  "ignoreSitemap": false,
  "includeSubdomains": true,
  "showSources": true,
  "scrapeOptions": {
    "formats": ["markdown"],
    "onlyMainContent": true,
    "timeout": 30000,
    "waitFor": 2000,
    "headers": {
      "User-Agent": "Data Extractor 1.0"
    }
  },
  "ignoreInvalidURLs": false
}
```

**Response (Firecrawl Compatible):**
```json
{
  "success": true,
  "data": [
    {
      "url": "https://example.com/article1",
      "extracted_data": {
        "title": "Understanding Web Scraping",
        "author": "John Doe",
        "publication_date": "2025-07-01",
        "content": "Web scraping is the process of extracting data from websites...",
        "tags": ["web-scraping", "automation", "data-extraction"]
      },
      "metadata": {
        "title": "Understanding Web Scraping - Tech Blog",
        "description": "A comprehensive guide to web scraping",
        "sourceURL": "https://example.com/article1",
        "statusCode": 200
      }
    },
    {
      "url": "https://example.com/article2",
      "extracted_data": {
        "title": "Advanced Crawling Techniques",
        "author": "Jane Smith",
        "publication_date": "2025-07-02",
        "content": "Advanced crawling involves sophisticated strategies...",
        "tags": ["crawling", "advanced", "techniques"]
      },
      "metadata": {
        "title": "Advanced Crawling Techniques - Tech Blog",
        "description": "Learn advanced crawling strategies",
        "sourceURL": "https://example.com/article2",
        "statusCode": 200
      }
    },
    {
      "url": "https://example.com/article3",
      "extracted_data": {
        "title": "Data Processing Pipeline",
        "author": "Bob Johnson",
        "publication_date": "2025-07-03",
        "content": "Building efficient data processing pipelines requires...",
        "tags": ["data-processing", "pipeline", "automation"]
      },
      "metadata": {
        "title": "Data Processing Pipeline - Tech Blog",
        "description": "Building data processing pipelines",
        "sourceURL": "https://example.com/article3",
        "statusCode": 200
      }
    }
  ],
  "invalidURLs": []
}
```

## Parameter Mapping

### Internal System Mapping
Our system maps Firecrawl parameters to internal crawler configurations:

```python
# Firecrawl → Internal Mapping
firecrawl_to_internal = {
    # Scrape Options
    "onlyMainContent": "content_filter.main_content_only",
    "includeTags": "content_filter.include_tags",
    "excludeTags": "content_filter.exclude_tags",
    "waitFor": "browser.wait_for_ms",
    "timeout": "browser.timeout_ms",
    "mobile": "browser.mobile",
    "skipTlsVerification": "browser.ignore_ssl_errors",
    "parsePDF": "extraction.parse_pdf",
    "removeBase64Images": "content_filter.remove_base64_images",
    "blockAds": "browser.block_ads",
    "storeInCache": "cache.enabled",
    
    # Actions
    "actions": "browser.actions",
    
    # Location
    "location.country": "browser.geolocation.country",
    "location.languages": "browser.languages",
    
    # Proxy
    "proxy": "browser.proxy.type",
    
    # Headers
    "headers": "browser.headers",
    
    # Crawl Options
    "excludePaths": "crawl.exclude_patterns",
    "includePaths": "crawl.include_patterns",
    "maxDepth": "crawl.max_depth",
    "limit": "crawl.max_pages",
    "allowExternalLinks": "crawl.allow_external",
    "allowSubdomains": "crawl.allow_subdomains",
    "delay": "crawl.delay_ms",
    "maxConcurrency": "crawl.concurrent_requests",
    
    # JSON Options
    "jsonOptions.schema": "extraction.llm.schema",
    "jsonOptions.systemPrompt": "extraction.llm.system_prompt",
    "jsonOptions.prompt": "extraction.llm.user_prompt",
    
    # Output Formats
    "formats": "output.formats"
}
```

### Response Format Mapping
Our internal response format is mapped to Firecrawl format:

```python
# Internal → Firecrawl Response Mapping
def map_to_firecrawl_response(internal_result):
    return {
        "markdown": internal_result.content.markdown,
        "html": internal_result.content.html,
        "rawHtml": internal_result.content.raw_html,
        "links": [link.url for link in internal_result.links.external + internal_result.links.internal],
        "screenshot": internal_result.screenshot,
        "metadata": {
            "title": internal_result.metadata.title,
            "description": internal_result.metadata.description,
            "language": internal_result.metadata.language,
            "sourceURL": internal_result.url,
            "statusCode": internal_result.metadata.status_code,
            "error": internal_result.error_message if not internal_result.success else None
        },
        "llm_extraction": json.loads(internal_result.extracted_content) if internal_result.extracted_content else None
    }
```

## Action Types Support

### Supported Actions
All Firecrawl action types are supported and mapped to crawl4ai operations:

```python
# Action Type Mapping
action_mapping = {
    "wait": {
        "type": "wait",
        "implementation": "browser.wait_for_selector",
        "parameters": ["milliseconds", "selector"]
    },
    "screenshot": {
        "type": "screenshot",
        "implementation": "browser.take_screenshot",
        "parameters": ["fullPage", "quality"]
    },
    "click": {
        "type": "click",
        "implementation": "browser.click_element",
        "parameters": ["selector", "all"]
    },
    "write": {
        "type": "type",
        "implementation": "browser.type_text",
        "parameters": ["text"]
    },
    "press": {
        "type": "key_press",
        "implementation": "browser.press_key",
        "parameters": ["key"]
    },
    "scroll": {
        "type": "scroll",
        "implementation": "browser.scroll",
        "parameters": ["direction", "selector"]
    },
    "scrape": {
        "type": "extract",
        "implementation": "content.extract",
        "parameters": []
    },
    "executeJavascript": {
        "type": "execute_js",
        "implementation": "browser.execute_javascript",
        "parameters": ["script"]
    },
    "pdf": {
        "type": "generate_pdf",
        "implementation": "browser.generate_pdf",
        "parameters": ["format", "landscape", "scale"]
    }
}
```

## Error Handling

### Firecrawl Error Format
All errors are returned in Firecrawl-compatible format:

```json
{
  "success": false,
  "error": "Error message here",
  "details": {
    "code": "ERROR_CODE",
    "message": "Detailed error message",
    "url": "https://example.com",
    "timestamp": "2025-07-03T10:30:00Z"
  }
}
```

### HTTP Status Code Mapping
```python
# Status Code Mapping
status_code_mapping = {
    # Success
    200: "OK",
    201: "Created",
    
    # Client Errors
    400: "Bad Request",
    401: "Unauthorized", 
    402: "Payment Required",
    404: "Not Found",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    
    # Server Errors
    500: "Internal Server Error",
    503: "Service Unavailable"
}
```

## Webhook Support

### Webhook Event Mapping
```python
# Webhook Events
webhook_events = {
    "page_completed": "Single page scraping completed",
    "batch_completed": "Batch scraping completed", 
    "crawl_completed": "Crawl job completed",
    "job_failed": "Job failed with error",
    "job_cancelled": "Job was cancelled"
}
```

### Webhook Payload Format
```json
{
  "event": "crawl_completed",
  "jobId": "crawl_12345678-1234-1234-1234-123456789012",
  "timestamp": "2025-07-03T11:00:00Z",
  "data": {
    "status": "completed",
    "total": 25,
    "completed": 25,
    "failed": 0,
    "results": [ /* crawl results */ ]
  },
  "metadata": {
    "crawl_name": "example_crawl"
  }
}
```

## Migration Guide

### From Firecrawl to Our System

1. **Update Base URL**: Change API base URL to our system
2. **API Key Migration**: Generate new API key in our system
3. **Code Compatibility**: No code changes required - all endpoints identical
4. **Enhanced Features**: Access to additional features through native API

### Example Migration
```python
# Before (Firecrawl)
import requests

response = requests.post(
    "https://api.firecrawl.dev/v1/scrape",
    headers={"Authorization": "Bearer fc-your-api-key"},
    json={"url": "https://example.com"}
)

# After (Our System)
import requests

response = requests.post(
    "https://api.crawler.example.com/v1/scrape",
    headers={"Authorization": "Bearer your-api-key"},
    json={"url": "https://example.com"}
)
```

## Rate Limiting

### Firecrawl-Compatible Rate Limits
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1625320800
X-RateLimit-Retry-After: 60
```

### Rate Limit Tiers
- **Free**: 100 requests/hour
- **Starter**: 1000 requests/hour  
- **Growth**: 10000 requests/hour
- **Scale**: 100000 requests/hour

## Implementation Architecture

### Priority and Approach
**HIGHEST PRIORITY**: This Firecrawl-compatible API must be implemented before any Native API features. The implementation should:

1. **Exact Specification Compliance**: Follow `groundtruth/firecrawl-openapi.json` exactly
2. **SQLite Backend**: Use SQLite for all storage needs (sessions, results, cache)
3. **Crawl4AI Integration**: Leverage crawl4ai 0.6.3+ capabilities from `groundtruth/crawl4ai_context.md`
4. **No Shortcuts**: Ensure 100% compatibility for seamless Firecrawl migration

### Adapter Layer
```python
class FirecrawlAdapter:
    """Adapter for Firecrawl API compatibility - HIGHEST PRIORITY implementation."""
    
    def __init__(self, scrape_service, crawl_service, storage_manager):
        self.scrape_service = scrape_service
        self.crawl_service = crawl_service
        self.storage_manager = storage_manager  # SQLite-based storage
    
    async def scrape(self, request: FirecrawlScrapeRequest) -> FirecrawlScrapeResponse:
        """Convert Firecrawl scrape request to internal format."""
        internal_request = self.convert_scrape_request(request)
        internal_result = await self.scrape_service.scrape_single(internal_request)
        return self.convert_scrape_response(internal_result)
    
    async def batch_scrape(self, request: FirecrawlBatchRequest) -> FirecrawlBatchResponse:
        """Convert Firecrawl batch request to internal format - async operation."""
        internal_request = self.convert_batch_request(request)
        batch_id = await self.scrape_service.scrape_batch_async(internal_request)
        return self.convert_batch_response(batch_id)
    
    async def crawl(self, request: FirecrawlCrawlRequest) -> FirecrawlCrawlResponse:
        """Convert Firecrawl crawl request to internal format."""
        internal_request = self.convert_crawl_request(request)
        internal_result = await self.crawl_service.start_crawl(internal_request)
        return self.convert_crawl_response(internal_result)
```

### Request/Response Conversion
```python
class FirecrawlConverter:
    """Convert between Firecrawl and internal formats."""
    
    def convert_scrape_options(self, fc_options: dict) -> ScrapeOptions:
        """Convert Firecrawl scrape options to internal format."""
        return ScrapeOptions(
            timeout=fc_options.get("timeout", 30000) // 1000,
            headless=not fc_options.get("mobile", False),
            user_agent=fc_options.get("headers", {}).get("User-Agent"),
            wait_for=fc_options.get("waitFor", 0) // 1000 if fc_options.get("waitFor") else None,
            screenshot="screenshot" in fc_options.get("formats", []),
            pdf="pdf" in fc_options.get("formats", []),
            cache_enabled=fc_options.get("storeInCache", True)
        )
    
    def convert_actions(self, fc_actions: list) -> list:
        """Convert Firecrawl actions to internal format."""
        internal_actions = []
        for action in fc_actions:
            if action["type"] == "wait":
                internal_actions.append({
                    "type": "wait",
                    "selector": action.get("selector"),
                    "timeout": action.get("milliseconds", 1000) / 1000
                })
            elif action["type"] == "click":
                internal_actions.append({
                    "type": "click",
                    "selector": action["selector"]
                })
            # Add other action conversions...
        return internal_actions
```

## Testing Strategy

### Strict Compatibility Testing (HIGHEST PRIORITY)
1. **Groundtruth Validation**: Test all endpoints against `groundtruth/firecrawl-openapi.json` specification
2. **Parameter Testing**: Verify every parameter in the OpenAPI spec works exactly as specified
3. **Response Format Testing**: Ensure responses match Firecrawl format byte-for-byte where possible
4. **Error Testing**: Test error responses match Firecrawl format exactly
5. **Integration Testing**: Test with existing Firecrawl client libraries
6. **Migration Testing**: Test seamless migration from real Firecrawl API
7. **Crawl4AI Feature Testing**: Verify all crawl4ai capabilities are accessible through Firecrawl interface

### Test Cases
```python
class TestFirecrawlCompatibility:
    """Test Firecrawl API compatibility."""
    
    async def test_scrape_endpoint(self):
        """Test /scrape endpoint compatibility."""
        request = {
            "url": "https://example.com",
            "formats": ["markdown", "html"],
            "onlyMainContent": True
        }
        response = await self.client.post("/scrape", json=request)
        assert response.status_code == 200
        assert "markdown" in response.json()["data"]
        assert "metadata" in response.json()["data"]
    
    async def test_batch_scrape_endpoint(self):
        """Test /batch/scrape endpoint compatibility."""
        request = {
            "urls": ["https://example.com/1", "https://example.com/2"],
            "maxConcurrency": 2
        }
        response = await self.client.post("/batch/scrape", json=request)
        assert response.status_code == 200
        assert "id" in response.json()
        assert "url" in response.json()
```

## Performance Considerations

### Optimization Strategies
1. **Request Caching**: Cache Firecrawl-format responses
2. **Async Processing**: Handle all requests asynchronously
3. **Connection Pooling**: Reuse browser connections
4. **Result Streaming**: Stream large result sets
5. **Compression**: Compress response data

### Scaling Considerations
1. **Load Balancing**: Distribute requests across instances
2. **Queue Management**: Handle job queues efficiently
3. **Resource Management**: Manage browser resources
4. **Monitoring**: Monitor performance metrics
5. **Auto-scaling**: Scale based on demand

## Documentation

### API Documentation
- **OpenAPI Spec**: Complete OpenAPI 3.0 specification
- **Interactive Docs**: Swagger UI for testing
- **Code Examples**: Examples in multiple languages
- **Migration Guide**: Guide for Firecrawl users

### Client Libraries
- **Python**: Official Python client library
- **JavaScript**: Official Node.js client library
- **Go**: Official Go client library
- **PHP**: Official PHP client library

## Future Enhancements

### Planned Features (Post-Compatibility)
1. **Groundtruth Monitoring**: Automated monitoring of `groundtruth/firecrawl-openapi.json` for spec changes
2. **Performance Improvements**: SQLite optimization for high-throughput Firecrawl operations
3. **Enhanced Crawl4AI Integration**: New crawl4ai features as they become available
4. **Advanced Error Handling**: More detailed error messages while maintaining Firecrawl compatibility
5. **Monitoring Integration**: Better observability tools for Firecrawl operations

### Implementation Roadmap
1. **Phase 1** (HIGHEST PRIORITY): Achieve 100% Firecrawl API compatibility
2. **Phase 2**: Performance optimization and SQLite tuning
3. **Phase 3**: Enhanced features that extend Firecrawl capabilities
4. **Phase 4**: Advanced monitoring and analytics

### Groundtruth Maintenance
- **Automated Spec Monitoring**: Monitor `groundtruth/firecrawl-openapi.json` for changes
- **Version Tracking**: Track Firecrawl API version changes and update accordingly
- **Crawl4AI Integration**: Leverage new features from `groundtruth/crawl4ai_context.md`
- **Compatibility Testing**: Continuous testing against Firecrawl specification

### Extensibility (Future)
1. **Custom Actions**: Support for additional action types beyond Firecrawl spec
2. **Enhanced Webhooks**: Extended webhook capabilities
3. **Custom Extractors**: Additional extraction strategies using crawl4ai features
4. **Analytics Extensions**: Advanced analytics while maintaining API compatibility