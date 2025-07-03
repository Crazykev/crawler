# Native REST API Design

## Overview

The Native REST API provides a comprehensive RESTful interface for the Crawler system. It follows REST principles with clear resource hierarchy, proper HTTP methods, and consistent response formats. The API supports all crawl4ai capabilities while maintaining the distinction between scraping (single page) and crawling (multiple pages).

**Important**: This Native API has **LOWEST PRIORITY** in the implementation sequence. The priority order is: CLI (highest) → Firecrawl API (high) → Native API (future). Implementation focus should be on CLI first, then Firecrawl compatibility.

## Groundtruth References

This design is based on the following groundtruth specifications:
- **Crawl4AI Context**: `groundtruth/crawl4ai_context.md` (Generated: 2025-06-16T09:14:43.423Z, Version: 0.6.3)
- **Firecrawl API Specification**: `groundtruth/firecrawl-openapi.json` (OpenAPI 3.0, Version: v1)

*Note: When groundtruth files are updated, this design and implementation must be reviewed and adjusted accordingly.*

## Base URL and Versioning

```
Base URL: https://api.crawler.example.com
Version: v1
Full Base URL: https://api.crawler.example.com/v1
```

## Authentication

### API Key Authentication
```http
Authorization: Bearer your_api_key_here
```

### Request Headers
```http
Content-Type: application/json
Accept: application/json
X-Request-ID: unique_request_id
```

## Resource Hierarchy

```
/v1/
├── scrape/                    # Single page scraping
│   └── single                 # Single URL scraping
├── batch/                     # Async batch operations
│   ├── scrape                 # Batch URL scraping
│   └── {batch_id}/            # Batch job status and results
├── crawl/                     # Multi-page crawling
│   └── {job_id}/              # Crawl job status and results (no separate jobs API)
├── sessions/                  # Browser session management
│   ├── create                 # Create session
│   └── {session_id}/          # Session operations
├── config/                    # Configuration management
│   ├── profiles               # Configuration profiles
│   └── settings               # System settings
└── system/                    # System information
    ├── health                 # Health check
    ├── metrics                # System metrics
    └── version                # Version information
```

**Note**: The `/v1/jobs/` API has been removed. Job status is accessed directly through the specific resource endpoints (e.g., `/v1/crawl/{job_id}` for crawl jobs, `/v1/batch/{batch_id}` for batch jobs).

## Scraping Endpoints

### Single Page Scraping

#### POST /v1/scrape/single
Scrape a single webpage with specified options.

**Request Body:**
```json
{
  "url": "https://example.com",
  "options": {
    "timeout": 30,
    "headless": true,
    "user_agent": "Crawler/1.0",
    "proxy": {
      "url": "http://proxy.example.com:8080",
      "username": "user",
      "password": "pass"
    },
    "viewport": {
      "width": 1920,
      "height": 1080
    }
  },
  "extraction": {
    "strategy": "css",
    "parameters": {
      "selectors": {
        "title": "h1",
        "content": ".article-content",
        "author": ".author-name"
      }
    }
  },
  "output": {
    "format": "json",
    "include_metadata": true,
    "include_links": true,
    "include_images": true
  },
  "actions": [
    {
      "type": "wait",
      "selector": ".content-loaded",
      "timeout": 10
    },
    {
      "type": "click",
      "selector": ".load-more-button"
    }
  ],
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "url": "https://example.com",
    "title": "Example Page",
    "timestamp": "2025-07-03T10:30:00Z",
    "status_code": 200,
    "content": {
      "markdown": "# Page Title\n\nContent...",
      "html": "<html>...</html>",
      "text": "Plain text content...",
      "extracted_data": {
        "title": "Example Page",
        "content": "Article content...",
        "author": "John Doe"
      }
    },
    "links": [
      {
        "url": "https://example.com/link1",
        "text": "Link 1",
        "type": "internal"
      }
    ],
    "images": [
      {
        "src": "https://example.com/image1.jpg",
        "alt": "Alt text",
        "width": 800,
        "height": 600
      }
    ],
    "metadata": {
      "load_time": 1.23,
      "size": 15678,
      "encoding": "utf-8",
      "final_url": "https://example.com",
      "redirects": []
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:30:00Z"
}
```

## Batch Operations

### Async Batch Scraping

#### POST /v1/batch/scrape
Initiate asynchronous batch scraping of multiple URLs. Returns immediately with a batch ID for status tracking.

**Request Body:**
```json
{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3"
  ],
  "options": {
    "timeout": 30,
    "headless": true,
    "concurrent_requests": 5
  },
  "extraction": {
    "strategy": "css",
    "parameters": {
      "selectors": {
        "title": "h1",
        "content": ".content"
      }
    }
  },
  "output": {
    "format": "json",
    "aggregate": true
  },
  "webhook": {
    "url": "https://your-webhook.com/callback",
    "events": ["completed", "failed"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "batch_id": "batch_123456",
    "status": "queued",
    "urls": [
      "https://example.com/page1",
      "https://example.com/page2",
      "https://example.com/page3"
    ],
    "total": 3,
    "status_url": "/v1/batch/batch_123456",
    "estimated_completion": "2025-07-03T10:35:00Z"
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:30:00Z"
}
```

#### GET /v1/batch/{batch_id}
Get batch scraping job status and results.

**Response:**
```json
{
  "success": true,
  "data": {
    "batch_id": "batch_123456",
    "status": "completed",
    "urls": [
      "https://example.com/page1",
      "https://example.com/page2",
      "https://example.com/page3"
    ],
    "total": 3,
    "completed": 3,
    "failed": 0,
    "results": [
      {
        "url": "https://example.com/page1",
        "success": true,
        "data": { /* scrape result */ }
      },
      {
        "url": "https://example.com/page2",
        "success": true,
        "data": { /* scrape result */ }
      },
      {
        "url": "https://example.com/page3",
        "success": true,
        "data": { /* scrape result */ }
      }
    ],
    "started_at": "2025-07-03T10:30:00Z",
    "completed_at": "2025-07-03T10:35:00Z",
    "duration": 300
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

## Crawling Endpoints

### Start Crawl Job

#### POST /v1/crawl
Start a new crawling job. Returns immediately with a job ID for status tracking.

**Request Body:**
```json
{
  "start_url": "https://example.com",
  "crawl_rules": {
    "max_depth": 3,
    "max_pages": 100,
    "max_duration": 3600,
    "include_patterns": [".*blog.*", ".*news.*"],
    "exclude_patterns": [".*admin.*", ".*login.*"],
    "allow_external_links": false,
    "allow_subdomains": true,
    "delay_between_requests": 1.0,
    "concurrent_requests": 5,
    "respect_robots_txt": true
  },
  "scrape_options": {
    "timeout": 30,
    "headless": true,
    "user_agent": "Crawler/1.0"
  },
  "extraction": {
    "strategy": "css",
    "parameters": {
      "selectors": {
        "title": "h1",
        "content": ".content",
        "date": ".publish-date"
      }
    }
  },
  "output": {
    "format": "json",
    "include_metadata": true,
    "create_index": true
  },
  "webhook": {
    "url": "https://your-webhook.com/callback",
    "events": ["page_completed", "crawl_completed", "crawl_failed"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "job_id": "crawl_123456",
    "start_url": "https://example.com",
    "status": "queued",
    "status_url": "/v1/crawl/crawl_123456",
    "created_at": "2025-07-03T10:30:00Z",
    "estimated_completion": "2025-07-03T11:30:00Z"
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:30:00Z"
}
```

### Get Crawl Job Status

#### GET /v1/crawl/{job_id}
Get crawling job status and results.

**Response:**
```json
{
  "success": true,
  "data": {
    "job_id": "crawl_123456",
    "start_url": "https://example.com",
    "status": "running",
    "created_at": "2025-07-03T10:30:00Z",
    "updated_at": "2025-07-03T10:35:00Z",
    "estimated_completion": "2025-07-03T11:30:00Z",
    "progress": {
      "total_pages": 45,
      "completed_pages": 30,
      "failed_pages": 2,
      "current_depth": 2,
      "discovered_urls": 45,
      "pages_per_second": 0.5
    },
    "results": [
      {
        "url": "https://example.com",
        "depth": 0,
        "success": true,
        "timestamp": "2025-07-03T10:30:00Z",
        "data": { /* scrape result */ }
      }
    ],
    "errors": [
      {
        "url": "https://example.com/error-page",
        "error": "Timeout after 30 seconds",
        "timestamp": "2025-07-03T10:32:00Z"
      }
    ],
    "metrics": {
      "total_requests": 32,
      "successful_requests": 30,
      "failed_requests": 2,
      "average_response_time": 1.23,
      "total_data_size": 1048576
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### List Crawl Jobs

#### GET /v1/crawl
List all crawling jobs with filtering and pagination.

**Query Parameters:**
- `status`: Filter by status (running, completed, failed, cancelled)
- `limit`: Number of results per page (default: 20)
- `offset`: Number of results to skip (default: 0)
- `sort`: Sort field (created_at, updated_at, start_url)
- `order`: Sort order (asc, desc)

**Response:**
```json
{
  "success": true,
  "data": {
    "jobs": [
      {
        "job_id": "crawl_123456",
        "start_url": "https://example.com",
        "status": "running",
        "created_at": "2025-07-03T10:30:00Z",
        "progress": {
          "total_pages": 45,
          "completed_pages": 30,
          "failed_pages": 2
        }
      }
    ],
    "pagination": {
      "total": 1,
      "limit": 20,
      "offset": 0,
      "has_next": false,
      "has_prev": false
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### Cancel Crawl Job

#### DELETE /v1/crawl/{job_id}
Cancel a running crawl job.

**Response:**
```json
{
  "success": true,
  "data": {
    "job_id": "crawl_123456",
    "status": "cancelled",
    "cancelled_at": "2025-07-03T10:35:00Z",
    "message": "Crawl job cancelled successfully"
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

## Session Management

### Create Session

#### POST /v1/sessions/create
Create a new browser session.

**Request Body:**
```json
{
  "config": {
    "browser_type": "chromium",
    "headless": true,
    "timeout": 30,
    "user_agent": "Crawler/1.0",
    "viewport": {
      "width": 1920,
      "height": 1080
    },
    "proxy": {
      "url": "http://proxy.example.com:8080"
    }
  },
  "session_timeout": 3600,
  "persist": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "session_123456",
    "status": "active",
    "created_at": "2025-07-03T10:30:00Z",
    "expires_at": "2025-07-03T11:30:00Z",
    "config": {
      "browser_type": "chromium",
      "headless": true,
      "timeout": 30
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:30:00Z"
}
```

### List Sessions

#### GET /v1/sessions
List all active sessions.

**Response:**
```json
{
  "success": true,
  "data": {
    "sessions": [
      {
        "session_id": "session_123456",
        "status": "active",
        "created_at": "2025-07-03T10:30:00Z",
        "expires_at": "2025-07-03T11:30:00Z",
        "last_used": "2025-07-03T10:35:00Z",
        "page_count": 5
      }
    ]
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### Get Session Details

#### GET /v1/sessions/{session_id}
Get session details and status.

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "session_123456",
    "status": "active",
    "created_at": "2025-07-03T10:30:00Z",
    "expires_at": "2025-07-03T11:30:00Z",
    "last_used": "2025-07-03T10:35:00Z",
    "page_count": 5,
    "config": {
      "browser_type": "chromium",
      "headless": true,
      "timeout": 30
    },
    "current_url": "https://example.com/page5",
    "history": [
      {
        "url": "https://example.com",
        "timestamp": "2025-07-03T10:30:00Z"
      }
    ]
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### Close Session

#### DELETE /v1/sessions/{session_id}
Close a browser session.

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "session_123456",
    "status": "closed",
    "closed_at": "2025-07-03T10:35:00Z",
    "message": "Session closed successfully"
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### Execute Session Action

#### POST /v1/sessions/{session_id}/actions
Execute actions in a browser session.

**Request Body:**
```json
{
  "actions": [
    {
      "type": "navigate",
      "url": "https://example.com/login"
    },
    {
      "type": "fill",
      "selector": "#username",
      "value": "user@example.com"
    },
    {
      "type": "fill",
      "selector": "#password",
      "value": "password123"
    },
    {
      "type": "click",
      "selector": "#login-button"
    },
    {
      "type": "wait",
      "selector": ".dashboard",
      "timeout": 10
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "session_123456",
    "actions_completed": 5,
    "current_url": "https://example.com/dashboard",
    "screenshots": [
      {
        "action_index": 4,
        "screenshot_base64": "data:image/png;base64,..."
      }
    ]
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

## Implementation Priority

**Note**: This Native API design has **LOWER PRIORITY** compared to the Firecrawl-compatible API. Development resources should focus on implementing Firecrawl compatibility first, as specified in the groundtruth files. This Native API can be implemented in later phases once Firecrawl compatibility is established.

## Configuration Management

### Get Configuration

#### GET /v1/config/settings
Get current system configuration.

**Response:**
```json
{
  "success": true,
  "data": {
    "version": "1.0.0",
    "settings": {
      "scrape": {
        "timeout": 30,
        "headless": true,
        "retry_count": 3
      },
      "crawl": {
        "max_depth": 3,
        "max_pages": 100,
        "concurrent_requests": 5
      },
      "system": {
        "max_workers": 10,
        "cache_enabled": true,
        "log_level": "INFO"
      }
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### Update Configuration

#### PUT /v1/config/settings
Update system configuration.

**Request Body:**
```json
{
  "settings": {
    "scrape": {
      "timeout": 45,
      "retry_count": 5
    },
    "crawl": {
      "max_pages": 200
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Configuration updated successfully",
    "updated_settings": {
      "scrape.timeout": 45,
      "scrape.retry_count": 5,
      "crawl.max_pages": 200
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### Configuration Profiles

#### GET /v1/config/profiles
List configuration profiles.

**Response:**
```json
{
  "success": true,
  "data": {
    "profiles": [
      {
        "name": "default",
        "description": "Default configuration",
        "active": true,
        "created_at": "2025-07-03T10:30:00Z"
      },
      {
        "name": "news",
        "description": "Optimized for news sites",
        "active": false,
        "created_at": "2025-07-03T10:30:00Z"
      }
    ]
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

#### POST /v1/config/profiles
Create a new configuration profile.

**Request Body:**
```json
{
  "name": "ecommerce",
  "description": "Optimized for e-commerce sites",
  "settings": {
    "scrape": {
      "timeout": 60,
      "screenshot": true
    },
    "crawl": {
      "max_depth": 5,
      "delay_between_requests": 0.5
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "profile": {
      "name": "ecommerce",
      "description": "Optimized for e-commerce sites",
      "created_at": "2025-07-03T10:35:00Z",
      "settings": {
        "scrape": {
          "timeout": 60,
          "screenshot": true
        },
        "crawl": {
          "max_depth": 5,
          "delay_between_requests": 0.5
        }
      }
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

## System Endpoints

### Health Check

#### GET /v1/system/health
System health check.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2025-07-03T10:35:00Z",
    "version": "1.0.0",
    "uptime": 86400,
    "components": {
      "database": "healthy",
      "cache": "healthy",
      "browser_pool": "healthy",
      "job_queue": "healthy"
    },
    "metrics": {
      "active_jobs": 5,
      "active_sessions": 3,
      "total_requests": 1000,
      "average_response_time": 1.23
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### System Metrics

#### GET /v1/system/metrics
Get system performance metrics.

**Response:**
```json
{
  "success": true,
  "data": {
    "timestamp": "2025-07-03T10:35:00Z",
    "metrics": {
      "requests": {
        "total": 1000,
        "successful": 950,
        "failed": 50,
        "rate_per_second": 2.5
      },
      "performance": {
        "average_response_time": 1.23,
        "p95_response_time": 2.5,
        "p99_response_time": 5.0
      },
      "resources": {
        "cpu_usage": 45.5,
        "memory_usage": 1024,
        "disk_usage": 5120,
        "active_connections": 25
      },
      "jobs": {
        "active": 5,
        "completed": 100,
        "failed": 3,
        "cancelled": 1
      }
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### Version Information

#### GET /v1/system/version
Get system version information.

**Response:**
```json
{
  "success": true,
  "data": {
    "version": "1.0.0",
    "build": "20250703-103500",
    "commit": "a1b2c3d4e5f6",
    "build_date": "2025-07-03T10:35:00Z",
    "dependencies": {
      "crawl4ai": "0.6.3",
      "fastapi": "0.104.0",
      "playwright": "1.40.0"
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

## Error Handling

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid URL format",
    "details": {
      "field": "url",
      "value": "invalid-url",
      "expected": "Valid HTTP/HTTPS URL"
    }
  },
  "request_id": "req_123456",
  "timestamp": "2025-07-03T10:35:00Z"
}
```

### HTTP Status Codes
- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict
- `422 Unprocessable Entity`: Validation errors
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Error Codes
- `VALIDATION_ERROR`: Invalid input parameters
- `AUTHENTICATION_ERROR`: Authentication failed
- `AUTHORIZATION_ERROR`: Insufficient permissions
- `RESOURCE_NOT_FOUND`: Requested resource not found
- `NETWORK_ERROR`: Network connectivity issues
- `TIMEOUT_ERROR`: Request timeout
- `EXTRACTION_ERROR`: Content extraction failed
- `RATE_LIMIT_ERROR`: Rate limit exceeded
- `INTERNAL_ERROR`: Internal server error

## Rate Limiting

### Rate Limit Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1625320800
X-RateLimit-Window: 3600
```

### Rate Limit Tiers
- **Free Tier**: 100 requests/hour
- **Basic Tier**: 1000 requests/hour
- **Premium Tier**: 10000 requests/hour
- **Enterprise Tier**: Custom limits

## Pagination

### Pagination Parameters
- `limit`: Number of results per page (1-100, default: 20)
- `offset`: Number of results to skip (default: 0)
- `cursor`: Cursor-based pagination token

### Pagination Response
```json
{
  "pagination": {
    "total": 100,
    "limit": 20,
    "offset": 0,
    "has_next": true,
    "has_prev": false,
    "next_cursor": "cursor_token_here"
  }
}
```

## Webhooks

### Webhook Configuration
```json
{
  "webhook": {
    "url": "https://your-webhook.com/callback",
    "events": ["job_completed", "job_failed", "page_scraped"],
    "headers": {
      "Authorization": "Bearer your_token",
      "X-Custom-Header": "custom_value"
    },
    "retry_count": 3,
    "timeout": 30
  }
}
```

### Webhook Payload
```json
{
  "event": "job_completed",
  "job_id": "job_123456",
  "timestamp": "2025-07-03T10:35:00Z",
  "data": {
    "status": "completed",
    "results": { /* job results */ }
  }
}
```

## SDK Examples

### Python SDK
```python
from crawler_sdk import CrawlerClient

client = CrawlerClient(
    base_url="https://api.crawler.example.com/v1",
    api_key="your_api_key"
)

# Single page scraping
result = client.scrape_single(
    url="https://example.com",
    extraction_strategy="css",
    selectors={"title": "h1", "content": ".content"}
)

# Multi-page crawling
job = client.start_crawl(
    start_url="https://example.com",
    max_depth=3,
    max_pages=100
)

# Monitor job progress
status = client.get_job_status(job.job_id)
```

### JavaScript SDK
```javascript
const { CrawlerClient } = require('@crawler/sdk');

const client = new CrawlerClient({
  baseURL: 'https://api.crawler.example.com/v1',
  apiKey: 'your_api_key'
});

// Single page scraping
const result = await client.scrapeSingle({
  url: 'https://example.com',
  extraction: {
    strategy: 'css',
    parameters: {
      selectors: {
        title: 'h1',
        content: '.content'
      }
    }
  }
});

// Multi-page crawling
const job = await client.startCrawl({
  startUrl: 'https://example.com',
  crawlRules: {
    maxDepth: 3,
    maxPages: 100
  }
});
```

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:
- Development: `https://api.crawler.example.com/v1/openapi.json`
- Interactive Documentation: `https://api.crawler.example.com/v1/docs`

## Authentication & Security

### API Key Management
- Generate API keys through the web dashboard
- Keys can be scoped to specific operations
- Keys can have expiration dates
- Keys can be rotated without service interruption

### Security Headers
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### IP Whitelisting
Configure allowed IP addresses for enhanced security:
```json
{
  "security": {
    "ip_whitelist": [
      "192.168.1.0/24",
      "10.0.0.0/8"
    ]
  }
}
```

## Future Enhancements

### Planned Features (Lower Priority)
- GraphQL API support
- Real-time streaming endpoints
- Advanced analytics endpoints
- Machine learning integration based on `groundtruth/crawl4ai_context.md` capabilities
- Custom plugin endpoints
- Enhanced crawl4ai integration for new features

### Extensibility
- Custom extraction strategies leveraging crawl4ai 0.6.3+ features
- Custom output formats
- Custom authentication providers
- SQLite to distributed storage migration
- Custom monitoring integrations

### Development Roadmap
1. **Phase 1**: Complete CLI interface (HIGHEST PRIORITY)
2. **Phase 2**: Complete Firecrawl-compatible API (HIGH PRIORITY)
3. **Phase 3**: Implement basic Native API endpoints (FUTURE)
4. **Phase 4**: Add advanced Native API features
5. **Phase 5**: GraphQL and real-time features

### Groundtruth Alignment
- Monitor `groundtruth/crawl4ai_context.md` for new crawl4ai features to integrate
- Ensure compatibility with `groundtruth/firecrawl-openapi.json` specifications
- Maintain feature parity with Firecrawl while adding Native API enhancements