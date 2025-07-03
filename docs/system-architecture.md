# Crawler System Architecture

## Overview

The Crawler system is a comprehensive web scraping and crawling solution built on top of the crawl4ai library. It provides three distinct interaction methods while maintaining a unified core architecture that leverages all crawl4ai capabilities.

## Groundtruth References

This design is based on the following groundtruth specifications:
- **Crawl4AI Context**: `groundtruth/crawl4ai_context.md` (Generated: 2025-06-16T09:14:43.423Z, Version: 0.6.3)
- **Firecrawl API Specification**: `groundtruth/firecrawl-openapi.json` (OpenAPI 3.0, Version: v1)

*Note: When groundtruth files are updated, this design and implementation must be reviewed and adjusted accordingly.*

## System Goals

- **Complete crawl4ai Integration**: Utilize all crawl4ai features including extraction strategies, browser configurations, session management, and output formats
- **Multi-Interface Support**: Provide CLI, native REST API, and Firecrawl-compatible API interfaces
- **Scalable Architecture**: Support both single-page scraping and multi-page crawling operations
- **Format Flexibility**: Support all input formats (URLs, files, raw HTML) and output formats (Markdown, JSON, screenshots, PDFs, links, media)
- **Enterprise Ready**: Built for production use with proper error handling, logging, and monitoring

## Core Concepts

### Terminology
- **Scrape**: Extract data from a single webpage
- **Crawl**: Navigate and extract data from multiple related webpages starting from a seed URL
- **Session**: Maintain browser state across multiple operations for complex interactions
- **Strategy**: Configurable approach for content extraction (CSS-based, LLM-based, etc.)

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Interface Layer                            │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   CLI Interface │  Native REST API │  Firecrawl Compatible API  │
│                 │                 │                             │
│ • scrape cmd    │ • /api/scrape   │ • /scrape                   │
│ • crawl cmd     │ • /api/crawl    │ • /crawl                    │
│ • config mgmt   │ • /api/sessions │ • /batch/scrape             │
│ • status check  │ • /api/jobs     │ • /extract                  │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  Service Layer                                 │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Scrape Service │  Crawl Service  │   Session Service           │
│                 │                 │                             │
│ • Single page   │ • Multi-page    │ • Browser sessions          │
│ • Batch scrape  │ • Site crawling │ • State management          │
│ • Format conv   │ • Link discovery│ • Session cleanup           │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Core Layer                                  │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Crawl4ai Core  │  Job Management │   Storage & Cache           │
│                 │                 │                             │
│ • AsyncWebCrawl │ • Queue mgmt    │ • Result storage            │
│ • Extraction    │ • Status track  │ • Session persistence       │
│ • Configuration │ • Error handling│ • Cache management          │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Component Details

### 1. Interface Layer

#### CLI Interface
- **Command Structure**: `crawler [scrape|crawl] [options]`
- **Configuration**: YAML/JSON config files and command-line arguments
- **Output**: Flexible output formats (JSON, Markdown, files)
- **Features**: Progress bars, verbose logging, batch processing

#### Native REST API
- **Design**: RESTful endpoints with clear resource hierarchy
- **Authentication**: API key-based authentication
- **Documentation**: OpenAPI/Swagger documentation
- **Features**: Async operations, job tracking, webhook support

#### Firecrawl Compatible API
- **Compatibility**: Full compatibility with Firecrawl API specification
- **Endpoints**: Exact match of Firecrawl endpoints and schemas
- **Migration**: Easy migration path from Firecrawl to our system

### 2. Service Layer

#### Scrape Service
- **Single Page Operations**: Direct URL scraping with various extraction strategies
- **Batch Operations**: Parallel processing of multiple URLs
- **Format Conversion**: Transform between different output formats
- **Validation**: Input validation and sanitization

#### Crawl Service
- **Multi-Page Crawling**: Intelligent navigation through related pages
- **Link Discovery**: Automatic detection of crawlable links
- **Depth Control**: Configurable crawling depth and scope
- **Filtering**: Include/exclude patterns for URLs and content

#### Session Service
- **Browser Management**: Persistent browser sessions for complex interactions
- **State Tracking**: Maintain state across multiple operations
- **Resource Cleanup**: Automatic cleanup of browser resources
- **Session Pooling**: Efficient reuse of browser instances

### 3. Core Layer

#### Crawl4ai Integration
- **Direct Integration**: Full utilization of crawl4ai's AsyncWebCrawler
- **Configuration Mapping**: Translation between our API and crawl4ai configs
- **Strategy Support**: Support for all crawl4ai extraction strategies
- **Extension Points**: Easy extension for new crawl4ai features

#### Job Management
- **Queue System**: Async job processing with priority support
- **Status Tracking**: Real-time job status and progress tracking
- **Error Handling**: Comprehensive error handling and retry logic
- **Concurrency**: Configurable concurrency limits and resource management

#### Storage & Cache
- **Result Storage**: SQLite-based persistent storage for crawl results
- **Cache Management**: SQLite-based intelligent caching for improved performance  
- **Session Persistence**: SQLite-based durable session state across restarts
- **Cleanup Policies**: Automatic cleanup of old data with SQLite cleanup procedures

## Data Flow

### Scrape Operation Flow
```
1. Request → Interface Layer → Validation
2. Validation → Service Layer → Job Creation
3. Job Creation → Core Layer → Crawl4ai Execution
4. Crawl4ai Execution → Result Processing → Format Conversion
5. Format Conversion → Storage → Response
```

### Crawl Operation Flow
```
1. Request → Interface Layer → Validation
2. Validation → Service Layer → Crawl Planning
3. Crawl Planning → Core Layer → Multi-Step Execution
4. Multi-Step Execution → Link Discovery → Queue Management
5. Queue Management → Parallel Processing → Result Aggregation
6. Result Aggregation → Storage → Response
```

## Configuration Management

### Configuration Hierarchy
1. **System Defaults**: Built-in sensible defaults
2. **Configuration Files**: YAML/JSON configuration files
3. **Environment Variables**: Environment-based overrides
4. **Command Line Arguments**: Runtime overrides
5. **API Parameters**: Request-specific parameters

### Configuration Categories
- **Browser Configuration**: Headless mode, proxy settings, user agents
- **Extraction Configuration**: Strategies, LLM settings, CSS selectors
- **Performance Configuration**: Concurrency, timeouts, retry policies
- **Output Configuration**: Formats, filtering, transformation rules

## Error Handling Strategy

### Error Categories
1. **Validation Errors**: Invalid input parameters
2. **Network Errors**: Connection issues, timeouts
3. **Extraction Errors**: Failed content extraction
4. **Resource Errors**: Memory, disk space limitations
5. **System Errors**: Internal system failures

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
  "timestamp": "2025-07-03T10:30:00Z",
  "requestId": "req-123456"
}
```

## Security Considerations

### Input Validation
- **URL Validation**: Strict URL format validation
- **Content Filtering**: Protection against malicious content
- **Rate Limiting**: Request rate limiting and throttling
- **Resource Limits**: Memory and CPU usage limits

### Authentication & Authorization
- **API Key Authentication**: Secure API key management
- **Role-Based Access**: Different access levels for different operations
- **Audit Logging**: Comprehensive audit trail

## Performance Optimization

### Caching Strategy
- **Result Caching**: Cache successful scrape results
- **Session Caching**: Reuse browser sessions when possible
- **Configuration Caching**: Cache parsed configurations
- **DNS Caching**: Cache DNS lookups

### Concurrency Management
- **Parallel Processing**: Concurrent execution of independent operations
- **Resource Pooling**: Efficient resource utilization
- **Backpressure Handling**: Graceful handling of high load
- **Queue Management**: Intelligent job queue management

## Monitoring & Observability

### Metrics Collection
- **Performance Metrics**: Response times, throughput, error rates
- **Resource Metrics**: Memory usage, CPU utilization
- **Business Metrics**: Scraping success rates, data quality
- **System Metrics**: Queue sizes, active sessions

### Logging Strategy
- **Structured Logging**: JSON-formatted logs for easy parsing
- **Log Levels**: Configurable log levels (DEBUG, INFO, WARN, ERROR)
- **Context Propagation**: Request tracing across components
- **Log Aggregation**: Centralized log collection and analysis

## Deployment Architecture

### Containerization
- **Docker Support**: Full Docker containerization
- **Multi-Stage Builds**: Optimized container images
- **Health Checks**: Built-in health check endpoints
- **Environment Configuration**: Environment-based configuration

### Scalability
- **Horizontal Scaling**: Support for multiple instances
- **Load Balancing**: Proper load balancing considerations
- **State Management**: Stateless design where possible
- **Resource Sharing**: Efficient resource sharing between instances

## Technology Stack

### Core Dependencies
- **Python 3.9+**: Primary runtime environment
- **crawl4ai**: Core web crawling library (version 0.6.3+)
- **FastAPI**: API framework for REST endpoints
- **Click**: CLI framework
- **Pydantic**: Data validation and serialization
- **SQLite**: Unified database for storage, session management, and caching

### Additional Dependencies
- **Playwright**: Browser automation (via crawl4ai)
- **asyncio**: Asynchronous programming
- **aiohttp**: HTTP client for external requests
- **SQLAlchemy**: Database ORM with SQLite backend
- **Alembic**: Database migrations for SQLite

## SQLite Architecture Design

### Database Strategy
The system uses a unified SQLite approach for Phase 1 implementation:

- **Single Database File**: All data stored in one SQLite database file for simplicity
- **Performance Considerations**: SQLite with WAL mode for concurrent read/write operations
- **Session Management**: Browser sessions stored in SQLite tables with TTL-based cleanup
- **Cache Implementation**: SQLite-based cache with LRU eviction policies
- **Result Storage**: Structured storage of crawl results with JSON fields for flexibility

### SQLite Schema Design
```sql
-- Core tables for unified SQLite storage
CREATE TABLE crawl_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    url TEXT NOT NULL,
    content_markdown TEXT,
    content_html TEXT,
    extracted_data JSON,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE browser_sessions (
    session_id TEXT PRIMARY KEY,
    config JSON,
    state_data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
);

CREATE TABLE cache_entries (
    cache_key TEXT PRIMARY KEY,
    data_value JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    access_count INTEGER DEFAULT 0
);
```

### Migration Strategy
- **Phase 1**: Start with SQLite for rapid development and deployment
- **Future Phases**: Consider migration to distributed databases when scale requirements grow
- **Data Compatibility**: Maintain data format compatibility for easy migration

## Development Phases

### Phase 1: Core Architecture (SQLite-First)
- Implement core service layer with SQLite backend
- Basic crawl4ai integration (version 0.6.3+)
- SQLite schema setup and migrations
- Basic CLI interface
- Basic error handling and logging

### Phase 2: API Development (Firecrawl Priority)
- **Firecrawl compatibility layer** (HIGH PRIORITY - based on `groundtruth/firecrawl-openapi.json`)
- Native REST API implementation (LOWER PRIORITY)
- SQLite-based session management
- Authentication system
- Async job management with SQLite

### Phase 3: Advanced Features
- Advanced extraction strategies (based on `groundtruth/crawl4ai_context.md`)
- SQLite-based caching system
- Performance optimization for SQLite
- Batch operations with `/v1/batch/` endpoints

### Phase 4: Production Ready
- Comprehensive monitoring
- Security hardening
- Documentation completion
- Deployment automation
- Future migration path from SQLite to distributed databases

## Next Steps

1. **SQLite Implementation**: Set up SQLite database schema and connection management
2. **Firecrawl API Specification**: Define complete Firecrawl-compatible API (HIGH PRIORITY)
3. **Native API Specification**: Define Native REST API (LOWER PRIORITY) 
4. **Crawl4AI Integration**: Implement core crawl4ai wrapper based on groundtruth context
5. **CLI Interface Design**: Design comprehensive CLI interface with SQLite backend
6. **Data Format Specifications**: Define all input/output formats with SQLite storage
7. **Implementation Planning**: Create detailed implementation roadmap prioritizing Firecrawl compatibility

## References

- **Groundtruth Files**: All implementation decisions should reference and validate against groundtruth specifications
- **Version Tracking**: Monitor groundtruth file changes for design updates
- **Crawl4AI Documentation**: Leverage crawl4ai 0.6.3+ features as documented in groundtruth context