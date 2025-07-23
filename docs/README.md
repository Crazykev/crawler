# Crawler System - Complete Architecture Documentation

## Overview

The Crawler System is a comprehensive web scraping and crawling solution built on top of the powerful crawl4ai library. It provides three distinct interaction methods while maintaining a unified core architecture that leverages all crawl4ai capabilities for maximum flexibility and functionality.

## System Goals

- **Complete crawl4ai Integration**: Utilize all crawl4ai features including extraction strategies, browser configurations, session management, and output formats
- **Multi-Interface Support**: Provide CLI, native REST API, and Firecrawl-compatible API interfaces
- **Scalable Architecture**: Support both single-page scraping and multi-page crawling operations
- **Format Flexibility**: Support all input formats (URLs, files, raw HTML) and output formats (Markdown, JSON, screenshots, PDFs, links, media)
- **Enterprise Ready**: Built for production use with proper error handling, logging, and monitoring

## Key Features

### 🚀 **Three Interface Methods**
1. **CLI Interface**: Powerful command-line interface with `scrape` and `crawl` commands
2. **Native REST API**: Comprehensive RESTful API following best practices
3. **Firecrawl Compatible API**: 100% compatibility with Firecrawl API for easy migration

### 🔧 **Complete crawl4ai Integration**
- Full support for `AsyncWebCrawler` capabilities
- All extraction strategies (CSS, LLM-based, custom)
- Browser configuration and session management
- JavaScript execution and page interactions
- Screenshot and PDF generation
- Comprehensive content filtering and processing

### 📊 **Rich Data Formats**
- **Input**: URLs, file paths, raw HTML, batch files (CSV, JSON, text)
- **Output**: Markdown, HTML, JSON, XML, CSV, SQLite, binary formats (PNG, PDF)
- **Templates**: Customizable output templates with Jinja2
- **Validation**: Comprehensive input/output validation

### 🏗️ **Robust Architecture**
- **Service Layer**: Clean separation of concerns with dedicated services
- **Core Layer**: Efficient crawl4ai integration and job management
- **Foundation Layer**: Configuration, error handling, and metrics collection
- **Scalability**: Horizontal scaling and load balancing support

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Interface Layer                            │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   CLI Interface │  Native REST API │  Firecrawl Compatible API  │
│                 │                 │                             │
│ • scrape cmd    │ • /api/scrape   │ • /scrape                   │
│ • crawl cmd     │ • /api/crawl    │ • /crawl                    │
│ • config mgmt   │ • /api/sessions │ • /batch/scrape             │
│ • status check  │ • status mgmt   │ • /extract                  │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  Service Layer                                 │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  ScrapeService  │  CrawlService   │   SessionService            │
│                 │                 │                             │
│ • Single page   │ • Multi-page    │ • Browser sessions          │
│ • Batch scrape  │ • Site crawling │ • State management          │
│ • Format conv   │ • Link discovery│ • Session cleanup           │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Core Layer                                  │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  CrawlEngine    │  JobManager     │   StorageManager            │
│                 │                 │                             │
│ • Crawl4ai wrap │ • Queue mgmt    │ • Result storage            │
│ • Config mgmt   │ • Status track  │ • Cache management          │
│ • Strategy exec │ • Error handling│ • Session persistence       │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                   Foundation Layer                             │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   ConfigManager │   ErrorHandler  │   MetricsCollector          │
│                 │                 │                             │
│ • Config loading│ • Error types   │ • Performance metrics       │
│ • Validation    │ • Retry logic   │ • Business metrics          │
│ • Env resolution│ • Error reporting│ • System metrics            │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Documentation Structure

This documentation is organized into several detailed documents:

### 📋 **Core Architecture Documents**

#### 1. [System Architecture](./system-architecture.md)
Complete system architecture overview including:
- High-level component design
- Data flow diagrams
- Configuration management
- Error handling strategy
- Security considerations
- Performance optimization
- Monitoring and observability

#### 2. [Core Components](./core-components.md)
Detailed design of core system components:
- **Service Layer**: ScrapeService, CrawlService, SessionService
- **Core Layer**: CrawlEngine, JobManager, StorageManager
- **Foundation Layer**: ConfigManager, ErrorHandler, MetricsCollector
- Component interfaces and data models
- Testing and deployment strategies

### 🖥️ **Interface Documentation**

#### 3. [CLI Interface](./cli-interface.md)
Comprehensive CLI design including:
- Command structure (`scrape`, `crawl`, `batch`, `session`, `config`)
- Configuration management (YAML, JSON, environment variables)
- Output formats and templates
- Progress reporting and logging
- Integration examples and performance tips

#### 4. [Native REST API](./native-api.md)
Complete RESTful API specification:
- Resource hierarchy and endpoints
- Request/response formats
- Authentication and security
- Error handling and status codes
- Rate limiting and pagination
- OpenAPI specification and SDK examples

#### 5. [Firecrawl Compatible API](./firecrawl-api.md)
Firecrawl compatibility layer design:
- Exact endpoint compatibility mapping
- Parameter and response format conversion
- Action type support and webhook integration
- Migration guide from Firecrawl
- Performance and testing considerations

### 📊 **Data and Integration**

#### 6. [Data Formats](./data-formats.md)
Comprehensive format handling:
- **Input Formats**: URLs, files, raw HTML, batch formats
- **Output Formats**: Markdown, HTML, JSON, XML, CSV, binary
- **Format Conversion**: Between all supported formats
- **Template System**: Customizable output templates
- **Validation**: Input/output validation and schemas
- **Performance**: Optimization and memory management

## Quick Start Examples

### CLI Usage
```bash
# Single page scraping
crawler scrape https://example.com --format json --output result.json

# Multi-page crawling
crawler crawl https://example.com --max-depth 3 --max-pages 100

# Batch processing
crawler batch urls.txt --output-dir ./results --workers 5

# With extraction strategy
crawler scrape https://example.com --extract-strategy llm --llm-model openai/gpt-4
```

### Native API Usage
```python
import requests

# Single page scraping
response = requests.post(
    "https://api.crawler.example.com/v1/scrape/single",
    headers={"Authorization": "Bearer your_api_key"},
    json={
        "url": "https://example.com",
        "extraction": {
            "strategy": "css",
            "parameters": {
                "selectors": {"title": "h1", "content": ".content"}
            }
        },
        "output": {"format": "json"}
    }
)

# Multi-page crawling
response = requests.post(
    "https://api.crawler.example.com/v1/crawl",
    headers={"Authorization": "Bearer your_api_key"},
    json={
        "start_url": "https://example.com",
        "crawl_rules": {"max_depth": 3, "max_pages": 100},
        "extraction": {"strategy": "llm", "parameters": {"prompt": "Extract main content"}}
    }
)
```

### Firecrawl Compatible Usage
```python
import requests

# Direct Firecrawl replacement
response = requests.post(
    "https://api.crawler.example.com/v1/scrape",
    headers={"Authorization": "Bearer your_api_key"},
    json={
        "url": "https://example.com",
        "formats": ["markdown", "json"],
        "onlyMainContent": True,
        "jsonOptions": {
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"}
                }
            }
        }
    }
)
```

## Key Design Principles

### 1. **Unified Core, Multiple Interfaces**
- Single core implementation supports all three interface types
- Consistent behavior across CLI, native API, and Firecrawl API
- Shared configuration and state management

### 2. **Complete crawl4ai Utilization**
- Direct integration with crawl4ai's AsyncWebCrawler
- Support for all extraction strategies and configurations
- Full browser automation and session management capabilities

### 3. **Terminology Consistency**
- **Scrape**: Single webpage data extraction
- **Crawl**: Multi-page site traversal and data collection
- **Session**: Persistent browser state for complex interactions
- **Strategy**: Configurable approach for content extraction

### 4. **Scalable Architecture**
- Horizontal scaling through multiple instances
- Efficient resource management and cleanup
- Configurable concurrency and rate limiting
- Enterprise-ready monitoring and observability

### 5. **Developer Experience**
- Comprehensive documentation and examples
- Multiple SDK options and integration patterns
- Clear error messages and debugging support
- Flexible configuration and customization options

## Technology Stack

### **Core Dependencies**
- **Python 3.9+**: Primary runtime environment
- **crawl4ai**: Core web crawling library
- **FastAPI**: API framework for REST endpoints
- **Click**: CLI framework
- **Pydantic**: Data validation and serialization

### **Storage & Caching**
- **SQLite**: Primary storage for all data (results, cache, sessions)
- **File System**: Result files and cache storage
- **SQLAlchemy**: Database ORM with SQLite backend
- **Future**: PostgreSQL migration path for production scale

### **Browser Automation**
- **Playwright**: Browser automation (via crawl4ai)
- **Chromium/Firefox**: Browser engines

### **Additional Tools**
- **Jinja2**: Template engine
- **asyncio**: Asynchronous programming
- **aiohttp**: HTTP client
- **pytest**: Testing framework

## Deployment Options

### **Container Deployment**
```dockerfile
# Multi-stage Docker build
FROM python:3.9-slim as builder
# Build dependencies...

FROM python:3.9-slim
# Runtime configuration...
COPY --from=builder /app /app
CMD ["python", "-m", "crawler.api"]
```

### **Kubernetes Deployment**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crawler-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: crawler-api
  template:
    metadata:
      labels:
        app: crawler-api
    spec:
      containers:
      - name: crawler-api
        image: crawler:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: crawler-secrets
              key: database-url
```

### **Docker Compose Setup**
```yaml
# 简化的Docker Compose（仅用于开发）
version: '3.8'
services:
  crawler-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data  # SQLite数据目录
    environment:
      - CRAWLER_DATA_DIR=/app/data
      - CRAWLER_LOG_LEVEL=WARNING
```

## Configuration Management

### **Configuration Hierarchy**
1. **System Defaults**: Built-in sensible defaults
2. **Configuration Files**: YAML/JSON configuration files
3. **Environment Variables**: Environment-based overrides
4. **Command Line Arguments**: Runtime overrides
5. **API Parameters**: Request-specific parameters

### **Example Configuration**
```yaml
# config.yaml
version: "1.0"

global:
  log_level: WARNING
  max_workers: 10

scrape:
  timeout: 30
  headless: true
  retry_count: 1
  cache_enabled: true

crawl:
  max_depth: 3
  max_pages: 100
  delay: 1.0
  concurrent_requests: 5

browser:
  user_agent: "Crawler/1.0"
  viewport:
    width: 1920
    height: 1080

llm:
  default_provider: openai
  openai:
    api_key: env:OPENAI_API_KEY
    model: gpt-4o-mini

storage:
  results_dir: ~/.crawler/results
  cache_dir: ~/.crawler/cache
  retention_days: 30
```

## Monitoring and Observability

### **Health Checks**
```bash
# System health
curl https://api.crawler.example.com/v1/system/health

# Component status
curl https://api.crawler.example.com/v1/system/metrics
```

### **Metrics Collection**
- **Performance Metrics**: Response times, throughput, error rates
- **Resource Metrics**: Memory usage, CPU utilization
- **Business Metrics**: Scraping success rates, data quality
- **System Metrics**: Queue sizes, active sessions

### **Logging Strategy**
- **Structured Logging**: JSON-formatted logs
- **Log Levels**: Configurable (DEBUG, INFO, WARN, ERROR)
- **Context Propagation**: Request tracing across components
- **Log Aggregation**: Centralized log collection

## Security Considerations

### **Authentication & Authorization**
- **API Key Authentication**: Secure API key management
- **Role-Based Access**: Different access levels
- **Rate Limiting**: Request rate limiting and throttling

### **Input Validation**
- **URL Validation**: Strict URL format validation
- **Content Filtering**: Protection against malicious content
- **Resource Limits**: Memory and CPU usage limits

### **Data Protection**
- **Sensitive Data Handling**: Secure processing of sensitive data
- **Encryption**: Encryption at rest and in transit
- **Data Retention**: Configurable data retention policies

## Performance Optimization

### **Caching Strategy**
- **Result Caching**: Cache successful scrape results
- **Session Caching**: Reuse browser sessions
- **Configuration Caching**: Cache parsed configurations
- **DNS Caching**: Cache DNS lookups

### **Concurrency Management**
- **Parallel Processing**: Concurrent execution of independent operations
- **Resource Pooling**: Efficient resource utilization
- **Backpressure Handling**: Graceful handling of high load
- **Queue Management**: Intelligent job queue management

### **Resource Management**
- **Memory Optimization**: Efficient memory usage patterns
- **Connection Pooling**: Reuse HTTP connections
- **Browser Pool Management**: Efficient browser instance reuse
- **Cleanup Strategies**: Automatic resource cleanup

## Development Workflow

### **Project Structure**
```
crawler/
├── src/
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── cli/           # CLI interface
│   │   ├── api/           # REST API endpoints
│   │   ├── services/      # Service layer
│   │   ├── core/          # Core crawling engine
│   │   ├── models/        # Data models
│   │   └── utils/         # Utility functions
│   └── tests/
├── docs/                  # Documentation
├── config/               # Configuration files
├── scripts/              # Deployment scripts
├── requirements.txt      # Python dependencies
├── Dockerfile           # Container definition
└── docker-compose.yml  # Local development setup
```

### **Testing Strategy**
- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Performance Tests**: Load testing and profiling
- **Compatibility Tests**: Firecrawl API compatibility

### **CI/CD Pipeline**
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/
      - name: Run linting
        run: flake8 src/
```

## Migration and Integration

### **From Firecrawl**
1. **Update Base URL**: Change API base URL to our system
2. **API Key Migration**: Generate new API key
3. **Code Compatibility**: No code changes required
4. **Enhanced Features**: Access additional features through native API

### **Integration Patterns**
- **Webhook Integration**: Real-time notifications
- **Database Integration**: Direct database storage
- **Message Queue Integration**: Apache Kafka, RabbitMQ
- **Analytics Integration**: Elasticsearch, data warehouses

## Future Roadmap

### **Phase 1: Core Implementation** (Q1 2025)
- [x] System architecture design
- [ ] Core service layer implementation
- [ ] Basic CLI interface

### **Phase 2: Feature Completion** (Q2 2025)
- [ ] Firecrawl compatibility layer
- [ ] REST API endpoints
- [ ] Advanced extraction strategies
- [ ] Session management system
- [ ] Comprehensive testing

### **Phase 3: Production Ready** (Q3 2025)
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Monitoring and observability
- [ ] Documentation completion

### **Phase 4: Advanced Features** (Q4 2025)
- [ ] Machine learning integration
- [ ] Real-time streaming capabilities
- [ ] Advanced analytics
- [ ] Plugin architecture

## Contributing

### **Development Setup**
```bash
# Clone repository
git clone https://github.com/example/crawler.git
cd crawler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Start development server
python -m crawler.api --dev
```

### **Contribution Guidelines**
1. **Code Style**: Follow PEP 8 and use Black for formatting
2. **Testing**: Maintain test coverage above 90%
3. **Documentation**: Update documentation for new features
4. **Commit Messages**: Use conventional commit format
5. **Pull Requests**: Include tests and documentation updates

## Support and Community

### **Getting Help**
- **Documentation**: Comprehensive docs at `/docs`
- **GitHub Issues**: Bug reports and feature requests
- **Community Forum**: Community support and discussions
- **Enterprise Support**: Commercial support options

### **Resources**
- **API Reference**: Complete API documentation
- **SDK Documentation**: Client library documentation
- **Examples Repository**: Sample code and integrations
- **Video Tutorials**: Step-by-step video guides

---

## Summary

The Crawler System provides a comprehensive, production-ready web scraping and crawling solution that fully leverages crawl4ai's capabilities while offering multiple interaction methods to suit different use cases. With its scalable architecture, rich feature set, and enterprise-ready design, it serves as a complete solution for web data extraction needs.

The system's three-layer architecture ensures clean separation of concerns, while the multiple interface options (CLI, native API, Firecrawl-compatible API) provide flexibility for different integration scenarios. Complete documentation, extensive testing, and performance optimization make it suitable for both development and production environments.

For detailed implementation guidance, refer to the individual documentation files linked throughout this document.