# CLI Interface Design

## Overview

The CLI interface provides a powerful command-line interface for the Crawler system, supporting both scraping and crawling operations with full access to all crawl4ai capabilities. The interface follows the principle that "scrape" refers to single-page operations while "crawl" refers to multi-page operations.

## Groundtruth References

This design is based on the following groundtruth specifications:
- **Crawl4AI Context**: `groundtruth/crawl4ai_context.md` (Generated: 2025-06-16T09:14:43.423Z, Version: 0.6.3)
- **Firecrawl API Specification**: `groundtruth/firecrawl-openapi.json` (OpenAPI 3.0, Version: v1)

*Note: CLI commands must support both Firecrawl-compatible operations and crawl4ai features. When groundtruth files are updated, CLI interface must be reviewed and adjusted accordingly.*

## Command Structure

### Base Command
```bash
crawler [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGUMENTS]
```

### Global Options
```bash
--config PATH         Configuration file path (default: ~/.crawler/config.yaml)
--verbose, -v         Verbose output (can be repeated: -v, -vv, -vvv)
--quiet, -q           Suppress output except errors
--log-level LEVEL     Set log level (DEBUG, INFO, WARN, ERROR)
--log-file PATH       Log file path
--no-color            Disable colored output
--help, -h            Show help message
--version             Show version information
```

## Core Commands

### 1. Scrape Command

#### Purpose
Scrape single webpages with various extraction strategies and output formats.

#### Basic Usage
```bash
crawler scrape [OPTIONS] URL
```

#### Options
```bash
# Output Options
--output, -o PATH           Output file path
--format, -f FORMAT         Output format (markdown, json, html, text, csv)
--template TEMPLATE         Output template file
--fields FIELDS             Comma-separated list of fields to extract

# Extraction Options
--extract-strategy STRATEGY  Extraction strategy (css, llm, auto)
--css-selector SELECTOR     CSS selector for extraction
--llm-model MODEL           LLM model for extraction (e.g., openai/gpt-4)
--llm-prompt PROMPT         Custom prompt for LLM extraction
--schema-file PATH          JSON schema file for structured extraction

# Browser Options
--headless/--no-headless    Run browser in headless mode (default: --headless)
--timeout SECONDS           Page load timeout (default: 30)
--user-agent STRING         Custom user agent
--proxy URL                 Proxy URL
--viewport WIDTHxHEIGHT     Browser viewport size

# Page Interaction
--wait-for SELECTOR         Wait for element to appear
--js-code FILE              JavaScript file to execute
--screenshot                Take screenshot
--pdf                       Generate PDF
--delay SECONDS             Delay before processing (default: 0)

# Session Management
--session-id ID             Use existing session
--create-session            Create new session
--session-timeout SECONDS   Session timeout (default: 3600)

# Cache Options
--cache/--no-cache          Enable/disable caching (default: --cache)
--cache-ttl SECONDS         Cache TTL in seconds (default: 3600)
--force-refresh             Force refresh cached content

# Retry Options
--retry-count COUNT         Number of retry attempts (default: 3)
--retry-delay SECONDS       Delay between retries (default: 1)
```

#### Examples
```bash
# Basic scraping
crawler scrape https://example.com

# Scrape with specific output format
crawler scrape https://example.com --format json --output result.json

# Scrape with CSS extraction
crawler scrape https://example.com --extract-strategy css --css-selector ".article-content"

# Scrape with LLM extraction
crawler scrape https://example.com --extract-strategy llm --llm-model openai/gpt-4 --llm-prompt "Extract the main article content"

# Scrape with screenshot
crawler scrape https://example.com --screenshot --output-dir ./screenshots/

# Scrape with JavaScript execution
crawler scrape https://example.com --js-code click_load_more.js --wait-for ".loaded-content"

# Scrape with session
crawler scrape https://example.com --session-id my-session --js-code login.js
```

### 2. Crawl Command

#### Purpose
Crawl multiple pages starting from a seed URL with intelligent link discovery.

#### Basic Usage
```bash
crawler crawl [OPTIONS] START_URL
```

#### Options
```bash
# Crawl Scope Options
--max-depth DEPTH           Maximum crawl depth (default: 3)
--max-pages COUNT           Maximum pages to crawl (default: 100)
--max-duration SECONDS      Maximum crawl duration (default: 3600)
--include-pattern PATTERN   Include URLs matching pattern (regex)
--exclude-pattern PATTERN   Exclude URLs matching pattern (regex)
--allow-external            Allow external links (default: false)
--allow-subdomains          Allow subdomains (default: true)

# Crawl Behavior
--delay SECONDS             Delay between requests (default: 1.0)
--concurrent REQUESTS       Max concurrent requests (default: 5)
--respect-robots            Respect robots.txt (default: true)
--follow-redirects          Follow HTTP redirects (default: true)
--ignore-ssl-errors         Ignore SSL certificate errors

# Link Discovery
--link-selector SELECTOR    CSS selector for links
--link-filter FILTER        Link filter expression
--sitemap-url URL           Use sitemap for link discovery
--ignore-sitemap            Ignore sitemap.xml

# Output Options
--output-dir PATH           Output directory (default: ./crawl_results)
--output-format FORMAT      Output format per page (markdown, json, html)
--aggregate-format FORMAT   Aggregate output format (json, csv, sqlite)
--create-index              Create index file

# Progress Tracking
--progress-file PATH        Progress file for resumable crawls
--status-interval SECONDS   Status update interval (default: 10)
--webhook-url URL           Webhook URL for status updates

# All scrape options are also available for individual pages
```

#### Examples
```bash
# Basic crawling
crawler crawl https://example.com

# Crawl with depth limit
crawler crawl https://example.com --max-depth 2 --max-pages 50

# Crawl with pattern filtering
crawler crawl https://example.com --include-pattern ".*blog.*" --exclude-pattern ".*admin.*"

# Crawl with custom output
crawler crawl https://example.com --output-dir ./results --output-format json --create-index

# Crawl with extraction strategy
crawler crawl https://example.com --extract-strategy css --css-selector ".content" --fields title,content,date

# Resumable crawl
crawler crawl https://example.com --progress-file ./crawl_progress.json --status-interval 5
```

### 3. Batch Command

#### Purpose
Process multiple URLs from a file or stdin with parallel execution.

#### Basic Usage
```bash
crawler batch [OPTIONS] [INPUT_FILE]
```

#### Options
```bash
# Input Options
--input-file PATH           Input file with URLs (default: stdin)
--input-format FORMAT       Input format (text, json, csv)
--url-column COLUMN         CSV column name for URLs
--batch-size SIZE           Batch size for processing (default: 10)

# Parallel Processing
--workers COUNT             Number of worker threads (default: 5)
--chunk-size SIZE           Chunk size for parallel processing

# Output Options
--output-dir PATH           Output directory
--output-format FORMAT      Output format (json, csv, sqlite)
--merge-results             Merge all results into single file

# All scrape options are available for individual URLs
```

#### Examples
```bash
# Process URLs from file
crawler batch urls.txt --output-dir ./batch_results

# Process URLs from CSV
crawler batch data.csv --input-format csv --url-column url --output-format json

# Process URLs from stdin
echo "https://example.com" | crawler batch --workers 3
```

### 4. Session Command

#### Purpose
Manage browser sessions for complex multi-step operations.

#### Subcommands
```bash
crawler session create [OPTIONS]     # Create new session
crawler session list                 # List active sessions
crawler session show SESSION_ID      # Show session details
crawler session close SESSION_ID     # Close session
crawler session cleanup              # Cleanup expired sessions
```

#### Examples
```bash
# Create session
crawler session create --session-id my-session --timeout 3600

# List sessions
crawler session list

# Use session for scraping
crawler scrape https://example.com --session-id my-session

# Close session
crawler session close my-session
```

### 5. Config Command

#### Purpose
Manage configuration settings and profiles.

#### Subcommands
```bash
crawler config init [PATH]           # Initialize configuration
crawler config show [KEY]            # Show configuration
crawler config set KEY VALUE         # Set configuration value
crawler config get KEY               # Get configuration value
crawler config validate              # Validate configuration
crawler config profile list          # List configuration profiles
crawler config profile create NAME   # Create configuration profile
crawler config profile use NAME      # Use configuration profile
```

#### Examples
```bash
# Initialize configuration
crawler config init

# Set default timeout
crawler config set scrape.timeout 60

# Show current configuration
crawler config show

# Create profile for news sites
crawler config profile create news
crawler config set --profile news scrape.user_agent "NewsBot/1.0"
```

### 6. Status Command

#### Purpose
Check status of running operations and system health.

#### Basic Usage
```bash
crawler status [OPTIONS] [JOB_ID]
```

#### Options
```bash
--watch, -w                 Watch mode (continuous updates)
--interval SECONDS          Update interval for watch mode (default: 2)
--format FORMAT             Output format (table, json, yaml)
--filter STATUS             Filter by status (running, completed, failed)
```

#### Examples
```bash
# Show all job statuses
crawler status

# Show specific job status
crawler status job-123456

# Watch running jobs
crawler status --watch --interval 5
```

## Configuration Management

### Configuration File Structure
```yaml
# ~/.crawler/config.yaml
version: "1.0"

# Global settings
global:
  log_level: INFO
  log_file: ~/.crawler/logs/crawler.log
  max_workers: 10

# Default scrape settings
scrape:
  timeout: 30
  headless: true
  retry_count: 3
  retry_delay: 1
  cache_enabled: true
  cache_ttl: 3600

# Default crawl settings
crawl:
  max_depth: 3
  max_pages: 100
  max_duration: 3600
  delay: 1.0
  concurrent_requests: 5
  respect_robots: true

# Browser settings
browser:
  user_agent: "Crawler/1.0"
  viewport:
    width: 1920
    height: 1080
  proxy:
    enabled: false
    url: ""
    username: ""
    password: ""

# LLM settings
llm:
  default_provider: openai
  openai:
    api_key: env:OPENAI_API_KEY
    model: gpt-4o-mini
  anthropic:
    api_key: env:ANTHROPIC_API_KEY
    model: claude-3-haiku-20240307

# Storage settings (SQLite-based)
storage:
  database_path: ~/.crawler/crawler.db
  results_dir: ~/.crawler/results
  cache_ttl: 3600
  session_timeout: 1800
  retention_days: 30
  sqlite_config:
    wal_mode: true
    journal_mode: WAL
    synchronous: NORMAL
    cache_size: 10000

# Output settings
output:
  default_format: markdown
  templates_dir: ~/.crawler/templates
  create_index: true
  compress_results: false

# Profiles
profiles:
  news:
    scrape:
      user_agent: "NewsBot/1.0"
      timeout: 45
    crawl:
      max_pages: 200
      delay: 2.0
  
  ecommerce:
    scrape:
      timeout: 60
      screenshot: true
    crawl:
      max_depth: 5
      delay: 0.5
```

### Environment Variables
```bash
# API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key

# Configuration
CRAWLER_CONFIG_PATH=~/.crawler/config.yaml
CRAWLER_LOG_LEVEL=INFO
CRAWLER_DATABASE_PATH=~/.crawler/crawler.db
CRAWLER_CACHE_TTL=3600

# Proxy Settings
CRAWLER_PROXY_URL=http://proxy.example.com:8080
CRAWLER_PROXY_USERNAME=username
CRAWLER_PROXY_PASSWORD=password
```

## Output Formats

### Markdown Format
```markdown
# Page Title

## Metadata
- URL: https://example.com
- Title: Example Page
- Timestamp: 2025-07-03T10:30:00Z
- Status: 200

## Content
[Extracted markdown content]

## Links
- [Link 1](https://example.com/link1)
- [Link 2](https://example.com/link2)

## Images
- ![Alt text](https://example.com/image1.jpg)
```

### JSON Format
```json
{
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
      "author": "John Doe",
      "date": "2025-07-03"
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
    "encoding": "utf-8"
  }
}
```

### CSV Format
```csv
url,title,timestamp,status_code,content_length,load_time
https://example.com,Example Page,2025-07-03T10:30:00Z,200,15678,1.23
```

## Error Handling

### Error Types
- **ValidationError**: Invalid input parameters
- **NetworkError**: Connection or timeout issues
- **ExtractionError**: Failed content extraction
- **ConfigurationError**: Invalid configuration
- **AuthenticationError**: API authentication failures
- **ResourceError**: System resource limitations

### Error Output Format
```json
{
  "error": {
    "type": "NetworkError",
    "message": "Connection timeout after 30 seconds",
    "code": "TIMEOUT",
    "url": "https://example.com",
    "timestamp": "2025-07-03T10:30:00Z",
    "details": {
      "timeout": 30,
      "retry_count": 3
    }
  }
}
```

## Progress Reporting

### Progress Bar
```
Crawling https://example.com...
Progress: [████████████░░░░░░░░] 60% (30/50 pages)
Current: https://example.com/page30
Elapsed: 00:02:30, ETA: 00:01:40
```

### Detailed Status
```
Crawl Status: Running
Start URL: https://example.com
Started: 2025-07-03 10:30:00
Elapsed: 00:02:30
Progress: 30/50 pages (60%)
Current Depth: 2/3
Active Workers: 5/5
Pages/sec: 0.2
Errors: 2
```

## Logging

### Log Levels
- **DEBUG**: Detailed debugging information
- **INFO**: General information messages
- **WARN**: Warning messages
- **ERROR**: Error messages

### Log Format
```
2025-07-03 10:30:00.123 [INFO] crawler.scrape: Starting scrape for https://example.com
2025-07-03 10:30:01.456 [DEBUG] crawler.scrape: Page loaded in 1.23 seconds
2025-07-03 10:30:02.789 [WARN] crawler.scrape: Retrying after timeout (attempt 2/3)
2025-07-03 10:30:03.012 [ERROR] crawler.scrape: Failed to scrape https://example.com: Connection timeout
```

## Performance Considerations

### Optimization Tips
- Use `--concurrent` for parallel crawling
- Enable caching with `--cache` for repeated operations
- Use `--batch-size` for efficient batch processing
- Configure appropriate `--delay` to avoid rate limiting
- Use `--headless` for better performance
- Consider `--timeout` settings for slow sites

### Resource Management
- Monitor memory usage with large crawls
- Use progress files for resumable long-running crawls
- Clean up sessions regularly
- Configure appropriate cache retention
- Monitor disk space usage

## Integration Examples

### Shell Scripting
```bash
#!/bin/bash
# Crawl multiple news sites
sites=(
  "https://news.example.com"
  "https://tech.example.com"
  "https://business.example.com"
)

for site in "${sites[@]}"; do
  crawler crawl "$site" \
    --max-pages 50 \
    --output-dir "./results/$(basename "$site")" \
    --extract-strategy css \
    --css-selector ".article-content"
done
```

### Cron Job
```bash
# Crontab entry for daily news crawling
0 6 * * * /usr/local/bin/crawler crawl https://news.example.com --max-pages 100 --output-dir /data/news/$(date +%Y%m%d)
```

### Data Pipeline
```bash
# Extract data and process with other tools
crawler batch urls.txt --output-format json | \
  jq '.[] | select(.status_code == 200)' | \
  python process_data.py
```

## Help System

### Built-in Help
```bash
# General help
crawler --help

# Command-specific help
crawler scrape --help
crawler crawl --help

# Show examples
crawler scrape --examples
crawler crawl --examples
```

### Man Page
```bash
# View manual page
man crawler
```

## Future Enhancements

### Planned Features
- Interactive mode with prompts
- Plugin system for custom extractors
- Real-time streaming output
- Integration with cloud storage
- Advanced scheduling capabilities
- Machine learning-based extraction

### Extensibility
- Custom output templates
- Plugin architecture
- Custom extraction strategies
- Integration with external tools
- Webhook support for notifications