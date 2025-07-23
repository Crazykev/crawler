"""CLI command for crawling multiple pages."""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ...services import get_crawl_service, CrawlRule
from ...foundation.config import get_config_manager
from ...foundation.logging import get_logger
from ...foundation.errors import handle_error

console = Console()
logger = get_logger(__name__)


@click.command()
@click.argument("start_url")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output directory for results"
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["markdown", "json", "html", "text"]),
    default="markdown",
    help="Output format"
)
@click.option(
    "--max-depth",
    type=int,
    default=3,
    help="Maximum crawl depth"
)
@click.option(
    "--max-pages",
    type=int,
    default=100,
    help="Maximum number of pages to crawl"
)
@click.option(
    "--max-duration",
    type=int,
    default=3600,
    help="Maximum crawl duration in seconds"
)
@click.option(
    "--delay",
    type=float,
    default=1.0,
    help="Delay between requests in seconds"
)
@click.option(
    "--concurrent-requests",
    type=int,
    default=5,
    help="Number of concurrent requests"
)
@click.option(
    "--extract-strategy",
    type=click.Choice(["auto", "css", "llm"]),
    default="auto",
    help="Content extraction strategy"
)
@click.option(
    "--css-selector",
    help="CSS selector for extraction (when using css strategy)"
)
@click.option(
    "--llm-model",
    help="LLM model for extraction (e.g., openai/gpt-4)"
)
@click.option(
    "--llm-prompt",
    help="Custom prompt for LLM extraction"
)
@click.option(
    "--include-pattern",
    multiple=True,
    help="Include URLs matching regex pattern (can be used multiple times)"
)
@click.option(
    "--exclude-pattern",
    multiple=True,
    help="Exclude URLs matching regex pattern (can be used multiple times)"
)
@click.option(
    "--allow-external/--no-external",
    default=False,
    help="Allow crawling external domains"
)
@click.option(
    "--allow-subdomains/--no-subdomains",
    default=True,
    help="Allow crawling subdomains"
)
@click.option(
    "--respect-robots/--ignore-robots",
    default=True,
    help="Respect robots.txt"
)
@click.option(
    "--timeout",
    type=int,
    help="Page load timeout in seconds"
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode"
)
@click.option(
    "--user-agent",
    help="Custom user agent string"
)
@click.option(
    "--session-id",
    help="Browser session ID to use"
)
@click.option(
    "--js-code",
    type=click.Path(exists=True),
    help="JavaScript file to execute before scraping"
)
@click.option(
    "--wait-for",
    help="CSS selector to wait for before processing"
)
@click.option(
    "--screenshot",
    is_flag=True,
    help="Take screenshots of pages"
)
@click.option(
    "--pdf",
    is_flag=True,
    help="Generate PDFs of pages"
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="Enable/disable caching"
)
@click.option(
    "--cache-ttl",
    type=int,
    help="Cache TTL in seconds"
)
@click.option(
    "--async-job",
    is_flag=True,
    help="Run as async job and return job ID"
)
@click.option(
    "--priority",
    type=int,
    default=0,
    help="Job priority (for async jobs)"
)
@click.option(
    "--monitor",
    is_flag=True,
    help="Monitor crawl progress in real-time"
)
@click.pass_context
def crawl(ctx, start_url, output, output_format, max_depth, max_pages, max_duration,
          delay, concurrent_requests, extract_strategy, css_selector, llm_model,
          llm_prompt, include_pattern, exclude_pattern, allow_external,
          allow_subdomains, respect_robots, timeout, headless, user_agent,
          session_id, js_code, wait_for, screenshot, pdf, cache, cache_ttl,
          async_job, priority, monitor):
    """Crawl multiple pages starting from a URL.
    
    Discovers and crawls linked pages with configurable depth and filtering.
    
    Examples:
    
        # Basic crawling with depth limit
        crawler crawl https://example.com --max-depth 2
        
        # Crawl with custom rules
        crawler crawl https://example.com --max-pages 50 --delay 2.0 --concurrent-requests 3
        
        # Crawl with URL filtering
        crawler crawl https://example.com --include-pattern ".*blog.*" --exclude-pattern ".*admin.*"
        
        # Crawl with LLM extraction
        crawler crawl https://example.com --extract-strategy llm --llm-model openai/gpt-4
        
        # Run as async job with monitoring
        crawler crawl https://example.com --async-job --monitor
    """
    verbose = ctx.obj.get('verbose', 0)
    quiet = ctx.obj.get('quiet', False)
    
    try:
        # Prepare crawl rules
        crawl_rules = CrawlRule(
            max_depth=max_depth,
            max_pages=max_pages,
            max_duration=max_duration,
            delay=delay,
            concurrent_requests=concurrent_requests,
            respect_robots=respect_robots,
            allow_external_links=allow_external,
            allow_subdomains=allow_subdomains,
            include_patterns=list(include_pattern),
            exclude_patterns=list(exclude_pattern)
        )
        
        # Prepare scraping options
        options = _prepare_crawl_options(
            timeout=timeout,
            headless=headless,
            user_agent=user_agent,
            js_code=js_code,
            wait_for=wait_for,
            screenshot=screenshot,
            pdf=pdf,
            cache=cache,
            cache_ttl=cache_ttl
        )
        
        # Prepare extraction strategy
        extraction_strategy = _prepare_extraction_strategy(
            strategy=extract_strategy,
            css_selector=css_selector,
            llm_model=llm_model,
            llm_prompt=llm_prompt
        )
        
        # Run crawling
        if async_job:
            result = asyncio.run(_run_async_crawl(
                start_url=start_url,
                crawl_rules=crawl_rules,
                options=options,
                extraction_strategy=extraction_strategy,
                output_format=output_format,
                session_id=session_id,
                priority=priority,
                monitor=monitor,
                quiet=quiet
            ))
        else:
            result = asyncio.run(_run_sync_crawl(
                start_url=start_url,
                crawl_rules=crawl_rules,
                options=options,
                extraction_strategy=extraction_strategy,
                output_format=output_format,
                session_id=session_id,
                monitor=monitor,
                quiet=quiet
            ))
        
        # Handle output
        _handle_crawl_output(result, output, output_format, quiet, async_job)
        
    except Exception as e:
        handle_error(e)
        if verbose > 0:
            console.print_exception()
        raise click.ClickException(f"Crawling failed: {str(e)}")


def _prepare_crawl_options(
    timeout: Optional[int],
    headless: bool,
    user_agent: Optional[str],
    js_code: Optional[str],
    wait_for: Optional[str],
    screenshot: bool,
    pdf: bool,
    cache: bool,
    cache_ttl: Optional[int]
) -> Dict[str, Any]:
    """Prepare crawling options."""
    options = {
        "headless": headless,
        "cache_enabled": cache
    }
    
    if timeout is not None:
        options["timeout"] = timeout
    if user_agent:
        options["user_agent"] = user_agent
    if js_code:
        # Read JavaScript file
        js_path = Path(js_code)
        options["js_code"] = js_path.read_text()
    if wait_for:
        options["wait_for"] = wait_for
    if screenshot:
        options["screenshot"] = True
    if pdf:
        options["pdf"] = True
    if cache_ttl is not None:
        options["cache_ttl"] = cache_ttl
    
    return options


def _prepare_extraction_strategy(
    strategy: str,
    css_selector: Optional[str],
    llm_model: Optional[str],
    llm_prompt: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Prepare extraction strategy."""
    if strategy == "auto":
        return None
    
    extraction_strategy = {"type": strategy}
    
    if strategy == "css":
        if css_selector:
            extraction_strategy["selectors"] = css_selector
        else:
            raise click.BadParameter("CSS selector required when using css strategy")
    
    elif strategy == "llm":
        if llm_model:
            extraction_strategy["model"] = llm_model
        if llm_prompt:
            extraction_strategy["prompt"] = llm_prompt
        
        # Check if API key is configured
        config_manager = get_config_manager()
        provider = llm_model.split("/")[0] if llm_model and "/" in llm_model else "openai"
        api_key = config_manager.get_setting(f"llm.{provider}_api_key")
        
        if not api_key:
            console.print(f"[yellow]Warning:[/yellow] No API key configured for {provider}")
    
    return extraction_strategy


async def _run_sync_crawl(
    start_url: str,
    crawl_rules: CrawlRule,
    options: Dict[str, Any],
    extraction_strategy: Optional[Dict[str, Any]],
    output_format: str,
    session_id: Optional[str],
    monitor: bool,
    quiet: bool
) -> Dict[str, Any]:
    """Run synchronous crawling."""
    crawl_service = get_crawl_service()
    await crawl_service.initialize()
    
    # Start crawl
    crawl_id = await crawl_service.start_crawl(
        start_url=start_url,
        crawl_rules=crawl_rules,
        options=options,
        extraction_strategy=extraction_strategy,
        output_format=output_format,
        session_id=session_id,
        store_results=True
    )
    
    # Monitor progress if requested
    if monitor and not quiet:
        await _monitor_crawl_progress(crawl_service, crawl_id)
    elif not quiet:
        console.print(f"[green]Crawl started:[/green] {crawl_id}")
        console.print("Use --monitor to see real-time progress")
    
    # Wait for completion
    while True:
        status = await crawl_service.get_crawl_status(crawl_id)
        if not status or status["status"] in ["completed", "failed", "cancelled"]:
            break
        await asyncio.sleep(1)
    
    # Get final results
    final_status = await crawl_service.get_crawl_status(crawl_id)
    results = await crawl_service.get_crawl_results(crawl_id)
    
    return {
        "crawl_id": crawl_id,
        "status": final_status,
        "results": results
    }


async def _run_async_crawl(
    start_url: str,
    crawl_rules: CrawlRule,
    options: Dict[str, Any],
    extraction_strategy: Optional[Dict[str, Any]],
    output_format: str,
    session_id: Optional[str],
    priority: int,
    monitor: bool,
    quiet: bool
) -> str:
    """Run asynchronous crawling."""
    crawl_service = get_crawl_service()
    await crawl_service.initialize()
    
    if not quiet:
        console.print(f"Submitting crawl job for {start_url}...")
    
    job_id = await crawl_service.start_crawl_async(
        start_url=start_url,
        crawl_rules=crawl_rules,
        options=options,
        extraction_strategy=extraction_strategy,
        output_format=output_format,
        session_id=session_id,
        priority=priority
    )
    
    if monitor and not quiet:
        console.print(f"[green]Job submitted:[/green] {job_id}")
        console.print("Monitoring progress...")
        # Note: For async jobs, we'd need to implement job monitoring
        # For now, just return the job ID
    
    return job_id


async def _monitor_crawl_progress(crawl_service, crawl_id: str) -> None:
    """Monitor crawl progress in real-time."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False
    ) as progress:
        
        task = progress.add_task("Crawling pages...", total=None)
        last_pages = 0
        
        while True:
            status = await crawl_service.get_crawl_status(crawl_id)
            if not status:
                break
            
            # Update progress
            current_pages = status.get("pages_crawled", 0)
            max_pages = status.get("pages_crawled", 0) + status.get("urls_queued", 0)
            
            if max_pages > 0:
                progress.update(task, total=max_pages, completed=current_pages)
            
            # Update description
            progress.update(task, description=f"Crawled {current_pages} pages (depth {status.get('current_depth', 0)})")
            
            # Check if done
            if status["status"] in ["completed", "failed", "cancelled"]:
                progress.update(task, completed=max_pages if max_pages > 0 else current_pages)
                break
            
            await asyncio.sleep(2)


def _handle_crawl_output(
    result: Any,
    output_path: Optional[str],
    output_format: str,
    quiet: bool,
    async_job: bool
) -> None:
    """Handle crawl output formatting and saving."""
    if async_job:
        # Result is job ID
        if not quiet:
            console.print(f"[green]Job submitted successfully![/green]")
            console.print(f"Job ID: {result}")
            console.print("Use 'crawler status' to check job status")
        else:
            console.print(result)
        return
    
    # Result is crawl data
    crawl_id = result.get("crawl_id")
    status = result.get("status", {})
    results = result.get("results", [])
    
    if not quiet:
        _show_crawl_summary(status, len(results))
    
    # Save results to output directory
    if output_path:
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save individual results
        for i, page_result in enumerate(results):
            if output_format == "json":
                content = json.dumps(page_result, indent=2, default=str)
                ext = "json"
            else:
                # Extract the appropriate content field based on format
                content_data = page_result.get("content", {})
                # Handle case where content might be a string instead of dict (error scenarios)
                if isinstance(content_data, str):
                    content = content_data
                elif isinstance(content_data, dict):
                    if output_format == "markdown":
                        content = content_data.get("markdown", "")
                    elif output_format == "html":
                        content = content_data.get("html", "")
                    elif output_format == "text":
                        content = content_data.get("text", "")
                    else:
                        # Default to markdown for backward compatibility
                        content = content_data.get("markdown", "") or content_data.get("text", "")
                else:
                    content = ""
                ext = "md" if output_format == "markdown" else output_format
            
            # Create safe filename from URL
            url = page_result.get("url", f"page_{i}")
            filename = _url_to_filename(url, ext)
            
            output_file = output_dir / filename
            output_file.write_text(content)
        
        # Save summary
        summary_file = output_dir / "crawl_summary.json"
        summary_data = {
            "crawl_id": crawl_id,
            "status": status,
            "results_count": len(results),
            "output_format": output_format
        }
        summary_file.write_text(json.dumps(summary_data, indent=2, default=str))
        
        if not quiet:
            console.print(f"[green]Results saved to:[/green] {output_path}")
            console.print(f"  - {len(results)} page files")
            console.print(f"  - crawl_summary.json")
    else:
        # Show first few results
        if results and not quiet:
            console.print("\n[bold]First 3 results:[/bold]")
            for i, page_result in enumerate(results[:3]):
                console.print(f"\n[cyan]Page {i+1}:[/cyan] {page_result.get('url', 'Unknown')}")
                # Extract the appropriate content field
                content_data = page_result.get("content", {})
                # Handle case where content might be a string instead of dict (error scenarios)
                if isinstance(content_data, str):
                    content = content_data
                elif isinstance(content_data, dict):
                    content = content_data.get("markdown", "") or content_data.get("text", "")
                else:
                    content = ""
                if len(content) > 200:
                    content = content[:200] + "..."
                console.print(content)


def _show_crawl_summary(status: Dict[str, Any], results_count: int) -> None:
    """Show crawl summary table."""
    table = Table(title="Crawl Summary")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Status", status.get("status", "Unknown"))
    table.add_row("Start URL", status.get("start_url", "N/A"))
    table.add_row("Pages Crawled", str(status.get("pages_crawled", 0)))
    table.add_row("Pages Successful", str(status.get("pages_successful", 0)))
    table.add_row("Pages Failed", str(status.get("pages_failed", 0)))
    table.add_row("Max Depth Reached", str(status.get("current_depth", 0)))
    table.add_row("URLs Discovered", str(status.get("urls_discovered", 0)))
    table.add_row("Results Stored", str(results_count))
    
    if "elapsed_time" in status:
        table.add_row("Elapsed Time", f"{status['elapsed_time']:.2f}s")
    
    if "success_rate" in status:
        table.add_row("Success Rate", f"{status['success_rate']:.1%}")
    
    console.print(table)


def _url_to_filename(url: str, ext: str) -> str:
    """Convert URL to safe filename."""
    import re
    
    # Remove protocol
    filename = re.sub(r'^https?://', '', url)
    
    # Replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Replace multiple underscores with single
    filename = re.sub(r'_+', '_', filename)
    
    # Truncate if too long
    if len(filename) > 100:
        filename = filename[:100]
    
    # Remove trailing underscore and add extension
    filename = filename.rstrip('_') + f".{ext}"
    
    return filename