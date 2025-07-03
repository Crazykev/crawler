# Basic Usage Examples

This document contains practical examples of using the Crawler system for common web scraping and crawling tasks.

## Single Page Scraping

### Simple Page Scraping

Extract content from a single webpage:

```bash
# Basic scraping with default settings
crawler scrape https://news.ycombinator.com

# Scrape and save to file
crawler scrape https://news.ycombinator.com --output hn_homepage.md

# Scrape with custom timeout
crawler scrape https://slow-website.com --timeout 60
```

### Content Extraction with CSS Selectors

Extract specific elements using CSS selectors:

```bash
# Extract article content
crawler scrape https://example-blog.com/article \
  --extract-strategy css \
  --css-selector "article .content"

# Extract multiple elements
crawler scrape https://news-site.com \
  --extract-strategy css \
  --css-selector "h1, .article-summary, .author"

# Save extracted content as JSON
crawler scrape https://product-page.com \
  --extract-strategy css \
  --css-selector ".product-details" \
  --format json \
  --output product.json
```

### Dynamic Content Scraping

Handle pages with JavaScript-generated content:

```bash
# Wait for dynamic content to load
crawler scrape https://spa-website.com \
  --wait-for ".dynamic-content" \
  --timeout 30

# Execute JavaScript before scraping
echo "document.querySelector('#load-more').click();" > load_more.js
crawler scrape https://infinite-scroll.com \
  --js-code load_more.js \
  --wait-for ".new-content"

# Take screenshot for verification
crawler scrape https://visual-site.com \
  --screenshot \
  --output-dir screenshots/
```

## Multi-Page Crawling

### Basic Website Crawling

Crawl an entire website with depth control:

```bash
# Crawl up to 3 levels deep
crawler crawl https://documentation-site.com \
  --max-depth 3 \
  --max-pages 50 \
  --output docs_crawl/

# Crawl with delay between requests
crawler crawl https://rate-limited-site.com \
  --max-depth 2 \
  --delay 2.0 \
  --concurrent-requests 2
```

### Targeted Crawling with Filters

Crawl specific sections of a website:

```bash
# Only crawl blog posts
crawler crawl https://company-blog.com \
  --include-pattern ".*blog.*" \
  --include-pattern ".*article.*" \
  --exclude-pattern ".*admin.*" \
  --max-depth 2

# Crawl documentation only
crawler crawl https://software-project.com \
  --include-pattern ".*/docs/.*" \
  --exclude-pattern ".*/api/.*" \
  --max-pages 100
```

### E-commerce Site Crawling

Crawl product pages from an e-commerce site:

```bash
# Crawl product catalog
crawler crawl https://shop.example.com \
  --include-pattern ".*/product/.*" \
  --include-pattern ".*/category/.*" \
  --exclude-pattern ".*/cart.*" \
  --exclude-pattern ".*/checkout.*" \
  --max-depth 4 \
  --extract-strategy css \
  --css-selector ".product-info, .price, .description" \
  --format json \
  --output products_crawl/
```

## Batch Processing

### Processing URL Lists

Create and process lists of URLs:

```bash
# Create URL list file
cat > news_sites.txt << EOF
https://news.ycombinator.com
https://techcrunch.com
https://arstechnica.com
https://theverge.com
EOF

# Process all URLs
crawler batch --file news_sites.txt \
  --output news_batch/ \
  --concurrent 3 \
  --delay 1.0
```

### Batch Crawling Multiple Sites

Crawl multiple websites in batch mode:

```bash
# Create site list for crawling
cat > tech_blogs.txt << EOF
https://blog.github.com
https://engineering.fb.com
https://blog.google
EOF

# Batch crawl with custom settings
crawler batch --file tech_blogs.txt \
  --mode crawl \
  --max-depth 2 \
  --max-pages 20 \
  --output tech_blogs_crawl/ \
  --continue-on-error \
  --save-errors
```

### Processing with Error Handling

Handle errors gracefully during batch processing:

```bash
# Create mixed URL list (some valid, some invalid)
cat > mixed_urls.txt << EOF
https://valid-site.com
https://invalid-domain-12345.com
https://another-valid-site.com
https://timeout-site.com
EOF

# Process with error handling
crawler batch --file mixed_urls.txt \
  --continue-on-error \
  --save-errors \
  --timeout 30 \
  --output results/ \
  --format json

# Check error log
cat results/batch_errors.json
```

## Session Management

### Maintaining State Across Requests

Use sessions for websites requiring login or state:

```bash
# Create a browser session
SESSION_ID=$(crawler session create --headless=false)
echo "Created session: $SESSION_ID"

# Use session for multiple operations
crawler scrape https://login-required-site.com/login \
  --session-id $SESSION_ID

# Continue with authenticated session
crawler scrape https://login-required-site.com/protected-page \
  --session-id $SESSION_ID

# Crawl with maintained session
crawler crawl https://login-required-site.com/dashboard \
  --session-id $SESSION_ID \
  --max-depth 2

# Clean up session
crawler session close $SESSION_ID
```

### Session Configuration

Create sessions with custom configurations:

```bash
# Create session with custom browser settings
crawler session create \
  --session-id mobile-session \
  --viewport-width 375 \
  --viewport-height 667 \
  --user-agent "Mobile Safari" \
  --timeout 45

# Use mobile session for scraping
crawler scrape https://responsive-site.com \
  --session-id mobile-session
```

## Advanced Content Extraction

### Using LLM for Content Extraction

Extract content using AI language models:

```bash
# Set up API key (do this once)
crawler config set llm.openai_api_key "your-openai-api-key"

# Extract and summarize article content
crawler scrape https://long-article.com \
  --extract-strategy llm \
  --llm-model "openai/gpt-4" \
  --llm-prompt "Extract the main points and create a summary"

# Extract structured data
crawler scrape https://product-page.com \
  --extract-strategy llm \
  --llm-model "openai/gpt-3.5-turbo" \
  --llm-prompt "Extract product name, price, and key features as JSON"
```

### Complex Extraction Workflows

Combine multiple extraction strategies:

```bash
# First pass: Extract main content with CSS
crawler scrape https://complex-page.com \
  --extract-strategy css \
  --css-selector "main article" \
  --output raw_content.md

# Second pass: Process with LLM
crawler scrape https://complex-page.com \
  --extract-strategy llm \
  --llm-prompt "Extract key insights and create executive summary" \
  --output processed_content.md
```

## Performance Optimization

### High-Performance Batch Processing

Optimize for large-scale scraping:

```bash
# High-concurrency batch processing
crawler batch --file large_url_list.txt \
  --concurrent 20 \
  --delay 0.1 \
  --cache \
  --cache-ttl 3600 \
  --output results/ \
  --async-jobs

# Monitor progress
crawler status monitor --interval 2
```

### Memory and Resource Management

Manage resources for long-running operations:

```bash
# Crawl with resource limits
crawler crawl https://large-site.com \
  --max-pages 1000 \
  --max-duration 7200 \
  --concurrent-requests 5 \
  --delay 1.0 \
  --monitor

# Use session cleanup
crawler session cleanup
```

## Data Processing and Analysis

### Extracting Structured Data

Extract and format data for analysis:

```bash
# Extract product data as JSON
crawler crawl https://ecommerce-site.com \
  --include-pattern ".*/product/.*" \
  --extract-strategy css \
  --css-selector ".product-title, .price, .rating" \
  --format json \
  --output products.json

# Extract news articles
crawler batch --file news_urls.txt \
  --extract-strategy css \
  --css-selector "h1, .article-body, .publish-date" \
  --format json \
  --output news_data/
```

### Export and Integration

Export data for further processing:

```bash
# Crawl and export to CSV format
crawler crawl https://directory-site.com \
  --include-pattern ".*/listing/.*" \
  --format json \
  --output listings/

# Convert to CSV (using external tool)
# python convert_to_csv.py listings/ > directory.csv
```

## Monitoring and Debugging

### Real-time Monitoring

Monitor crawling operations in real-time:

```bash
# Start large crawl operation
crawler crawl https://large-site.com \
  --max-pages 500 \
  --async-job

# Monitor in separate terminal
crawler status monitor --interval 5

# Check specific job status
JOB_ID="your-job-id"
crawler status job $JOB_ID
```

### Debug Mode Operations

Debug problematic websites:

```bash
# Enable maximum verbosity
crawler -vvv scrape https://problematic-site.com

# Run with detailed logging
crawler --config debug-config.yaml scrape https://complex-site.com

# Take screenshots for debugging
crawler scrape https://visual-issue-site.com \
  --screenshot \
  --no-headless \
  --output debug_output/
```

## Configuration Management

### Project-Specific Configuration

Create configuration for different projects:

```bash
# Initialize project config
crawler config init --config-path ./project-config.yaml

# Edit configuration
cat > project-config.yaml << EOF
scrape:
  timeout: 60
  user_agent: "ProjectBot/1.0"
  
crawl:
  max_depth: 4
  delay: 2.0
  respect_robots: true
  
browser:
  viewport_width: 1280
  viewport_height: 720
EOF

# Use project config
crawler --config ./project-config.yaml crawl https://target-site.com
```

### Environment-Specific Settings

Configure for different environments:

```bash
# Development configuration
crawler config set scrape.timeout 10
crawler config set crawl.concurrent_requests 2

# Production configuration  
crawler config set scrape.timeout 30
crawler config set crawl.concurrent_requests 10
crawler config set logging.level "WARNING"
```

## Integration Examples

### Automated Workflows

Create automated scraping workflows:

```bash
#!/bin/bash
# Daily news scraping workflow

# Create timestamp
DATE=$(date +%Y-%m-%d)
OUTPUT_DIR="news_$DATE"

# Scrape news sites
crawler batch --file news_sites.txt \
  --output "$OUTPUT_DIR" \
  --format json \
  --continue-on-error

# Check results
echo "Scraped $(ls $OUTPUT_DIR/*.json | wc -l) articles"

# Cleanup old data
find news_* -type d -mtime +7 -exec rm -rf {} \;
```

### Data Pipeline Integration

Integrate with data processing pipelines:

```bash
# Scrape and process pipeline
crawler crawl https://data-source.com \
  --format json \
  --output raw_data/ && \
python process_data.py raw_data/ && \
python analyze_data.py processed_data/
```

These examples demonstrate the flexibility and power of the Crawler system. You can combine these patterns and adapt them to your specific use cases.