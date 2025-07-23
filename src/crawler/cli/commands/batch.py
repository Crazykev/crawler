"""CLI command for batch processing multiple URLs."""

import asyncio
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ...services import get_scrape_service, get_crawl_service, CrawlRule
from ...foundation.config import get_config_manager
from ...foundation.logging import get_logger
from ...foundation.errors import handle_error

console = Console()
logger = get_logger(__name__)


@click.command()
@click.argument("urls", nargs=-1, required=False)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="File containing URLs (one per line)"
)
@click.option(
    "--output",
    "-o",
    "--output-dir",
    type=click.Path(),
    required=True,
    help="Output directory for results"
)
@click.option(
    "--mode",
    type=click.Choice(["scrape", "crawl"]),
    default="scrape",
    help="Processing mode (scrape individual pages or crawl sites)"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "html", "text"]),
    default="markdown",
    help="Output format"
)
@click.option(
    "--concurrent",
    type=int,
    default=5,
    help="Number of concurrent operations"
)
@click.option(
    "--delay",
    type=float,
    default=1.0,
    help="Delay between operations in seconds"
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
    "--max-depth",
    type=int,
    default=2,
    help="Maximum crawl depth (crawl mode only)"
)
@click.option(
    "--max-pages",
    type=int,
    default=50,
    help="Maximum pages per site (crawl mode only)"
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
    "--cache/--no-cache",
    default=True,
    help="Enable/disable caching"
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Continue processing even if some URLs fail"
)
@click.option(
    "--save-errors",
    is_flag=True,
    help="Save error details to file"
)
@click.option(
    "--async-jobs",
    is_flag=True,
    help="Submit as async jobs instead of processing directly"
)
@click.pass_context
def batch(ctx, urls, file, output, mode, output_format, concurrent, delay,
          extract_strategy, css_selector, llm_model, llm_prompt, max_depth,
          max_pages, timeout, headless, user_agent, session_id, cache,
          continue_on_error, save_errors, async_jobs):
    """Process multiple URLs in batch mode.
    
    Can process URLs from command line arguments or from a file.
    Supports both scraping individual pages and crawling entire sites.
    
    Examples:
    
        # Scrape multiple URLs from command line
        crawler batch https://example.com https://test.com --output results/
        
        # Process URLs from file
        crawler batch --file urls.txt --output results/ --mode crawl
        
        # Batch crawl with custom settings
        crawler batch --file sites.txt --output results/ --mode crawl --max-depth 3 --concurrent 3
        
        # Batch with error handling
        crawler batch --file urls.txt --output results/ --continue-on-error --save-errors
        
        # Submit as async jobs
        crawler batch --file urls.txt --output results/ --async-jobs
    """
    verbose = ctx.obj.get('verbose', 0)
    quiet = ctx.obj.get('quiet', False)
    
    try:
        # Get URLs from file or command line
        url_list = _get_urls_from_input(urls, file)
        
        if not url_list:
            console.print("[red]Error:[/red] No URLs provided. Use --file or provide URLs as arguments.")
            # Don't exit in tests - raise exception instead
            if ctx.obj and ctx.obj.get('testing', False):
                from ...foundation.errors import ValidationError
                raise ValidationError("No URLs provided")
            ctx.exit(1)
        
        if not quiet:
            console.print(f"[green]Processing {len(url_list)} URLs in {mode} mode[/green]")
        
        # Prepare options
        options = _prepare_batch_options(
            timeout=timeout,
            headless=headless,
            user_agent=user_agent,
            cache=cache
        )
        
        # Prepare extraction strategy
        extraction_strategy = _prepare_extraction_strategy(
            strategy=extract_strategy,
            css_selector=css_selector,
            llm_model=llm_model,
            llm_prompt=llm_prompt
        )
        
        # Create output directory
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process batch
        if async_jobs:
            results = asyncio.run(_process_batch_async(
                url_list=url_list,
                mode=mode,
                output_dir=output_dir,
                options=options,
                extraction_strategy=extraction_strategy,
                output_format=output_format,
                session_id=session_id,
                max_depth=max_depth,
                max_pages=max_pages,
                continue_on_error=continue_on_error,
                quiet=quiet
            ))
        else:
            results = asyncio.run(_process_batch_sync(
                url_list=url_list,
                mode=mode,
                output_dir=output_dir,
                options=options,
                extraction_strategy=extraction_strategy,
                output_format=output_format,
                concurrent=concurrent,
                delay=delay,
                session_id=session_id,
                max_depth=max_depth,
                max_pages=max_pages,
                continue_on_error=continue_on_error,
                quiet=quiet
            ))
        
        # Handle results
        _handle_batch_results(results, output_dir, save_errors, quiet)
        
    except Exception as e:
        handle_error(e)
        if verbose > 0:
            console.print_exception()
        console.print(f"[red]Error:[/red] Batch processing failed: {str(e)}")
        # Don't exit in tests - let the exception propagate
        if ctx.obj and ctx.obj.get('testing', False):
            raise
        ctx.exit(1)
    
    # If we get here, the command was successful
    # Don't exit in tests - let the function return normally
    if not (ctx.obj and ctx.obj.get('testing', False)):
        ctx.exit(0)


def _get_urls_from_input(urls: tuple, file_path: Optional[str]) -> List[str]:
    """Get URLs from command line arguments or file."""
    url_list = []
    
    # Add URLs from command line - but check if they're file paths first
    if urls:
        for url in urls:
            # Check if this "URL" is actually a file path
            if Path(url).exists() and not url.startswith(('http://', 'https://')):
                # It's a file path, read URLs from it
                file_obj = Path(url)
                content = file_obj.read_text().strip()
                
                # Handle different file formats
                if url.endswith('.json'):
                    # JSON format
                    data = json.loads(content)
                    if isinstance(data, list):
                        url_list.extend(data)
                    elif isinstance(data, dict) and 'urls' in data:
                        url_list.extend(data['urls'])
                else:
                    # Plain text format (one URL per line)
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            url_list.append(line)
            else:
                # It's a regular URL
                url_list.append(url)
    
    # Add URLs from file
    if file_path:
        file_obj = Path(file_path)
        content = file_obj.read_text().strip()
        
        # Handle different file formats
        if file_path.endswith('.json'):
            # JSON format
            data = json.loads(content)
            if isinstance(data, list):
                url_list.extend(data)
            elif isinstance(data, dict) and 'urls' in data:
                url_list.extend(data['urls'])
        else:
            # Plain text format (one URL per line)
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    url_list.append(line)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in url_list:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls


def _prepare_batch_options(
    timeout: Optional[int],
    headless: bool,
    user_agent: Optional[str],
    cache: bool
) -> Dict[str, Any]:
    """Prepare batch processing options."""
    options = {
        "headless": headless,
        "cache_enabled": cache
    }
    
    if timeout is not None:
        options["timeout"] = timeout
    if user_agent:
        options["user_agent"] = user_agent
    
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


async def _process_batch_sync(
    url_list: List[str],
    mode: str,
    output_dir: Path,
    options: Dict[str, Any],
    extraction_strategy: Optional[Dict[str, Any]],
    output_format: str,
    concurrent: int,
    delay: float,
    session_id: Optional[str],
    max_depth: int,
    max_pages: int,
    continue_on_error: bool,
    quiet: bool
) -> Dict[str, Any]:
    """Process batch synchronously."""
    results = {
        "total": len(url_list),
        "successful": 0,
        "failed": 0,
        "results": [],
        "errors": []
    }
    
    # Initialize services
    scrape_service = get_scrape_service()
    crawl_service = get_crawl_service()
    await scrape_service.initialize()
    await crawl_service.initialize()
    
    # Process with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False
    ) as progress:
        
        task = progress.add_task(f"Processing {len(url_list)} URLs...", total=len(url_list))
        
        # Process URLs in batches
        semaphore = asyncio.Semaphore(concurrent)
        
        async def process_url(url: str, index: int):
            async with semaphore:
                try:
                    if mode == "scrape":
                        result = await scrape_service.scrape_single(
                            url=url,
                            options=options,
                            extraction_strategy=extraction_strategy,
                            output_format=output_format,
                            session_id=session_id
                        )
                    else:  # crawl mode
                        crawl_rules = CrawlRule(
                            max_depth=max_depth,
                            max_pages=max_pages,
                            concurrent_requests=1  # Single URL, use 1 concurrent request
                        )
                        
                        crawl_id = await crawl_service.start_crawl(
                            start_url=url,
                            crawl_rules=crawl_rules,
                            options=options,
                            extraction_strategy=extraction_strategy,
                            output_format=output_format,
                            session_id=session_id
                        )
                        
                        # Wait for crawl completion
                        while True:
                            status = await crawl_service.get_crawl_status(crawl_id)
                            if not status or status["status"] in ["completed", "failed", "cancelled"]:
                                break
                            await asyncio.sleep(1)
                        
                        # Get crawl results
                        crawl_results = await crawl_service.get_crawl_results(crawl_id)
                        result = {
                            "success": True,
                            "crawl_id": crawl_id,
                            "results": crawl_results,
                            "url": url
                        }
                    
                    # Save result
                    _save_result(result, url, index, output_dir, output_format)
                    
                    results["results"].append({
                        "url": url,
                        "success": True,
                        "result": result
                    })
                    results["successful"] += 1
                    
                except Exception as e:
                    error_info = {
                        "url": url,
                        "error": str(e),
                        "success": False
                    }
                    results["errors"].append(error_info)
                    results["failed"] += 1
                    
                    if not continue_on_error:
                        raise
                
                finally:
                    progress.update(task, advance=1)
                    
                    # Apply delay
                    if delay > 0:
                        await asyncio.sleep(delay)
        
        # Process all URLs
        tasks = [process_url(url, i) for i, url in enumerate(url_list)]
        await asyncio.gather(*tasks, return_exceptions=continue_on_error)
    
    return results


async def _process_batch_async(
    url_list: List[str],
    mode: str,
    output_dir: Path,
    options: Dict[str, Any],
    extraction_strategy: Optional[Dict[str, Any]],
    output_format: str,
    session_id: Optional[str],
    max_depth: int,
    max_pages: int,
    continue_on_error: bool,
    quiet: bool
) -> Dict[str, Any]:
    """Process batch asynchronously via job queue."""
    results = {
        "total": len(url_list),
        "successful": 0,
        "failed": 0,
        "job_ids": [],
        "results": []
    }
    
    # Initialize services
    scrape_service = get_scrape_service()
    crawl_service = get_crawl_service()
    await scrape_service.initialize()
    await crawl_service.initialize()
    
    if not quiet:
        console.print(f"Submitting {len(url_list)} jobs...")
    
    # Submit jobs
    for i, url in enumerate(url_list):
        try:
            if mode == "scrape":
                job_id = await scrape_service.scrape_single_async(
                    url=url,
                    options=options,
                    extraction_strategy=extraction_strategy,
                    output_format=output_format,
                    session_id=session_id
                )
            else:  # crawl mode
                crawl_rules = CrawlRule(
                    max_depth=max_depth,
                    max_pages=max_pages
                )
                
                job_id = await crawl_service.start_crawl_async(
                    start_url=url,
                    crawl_rules=crawl_rules,
                    options=options,
                    extraction_strategy=extraction_strategy,
                    output_format=output_format,
                    session_id=session_id
                )
            
            results["job_ids"].append(job_id)
            results["results"].append({
                "url": url,
                "job_id": job_id,
                "success": True
            })
            results["successful"] += 1
            
        except Exception as e:
            error_info = {
                "url": url,
                "error": str(e),
                "success": False
            }
            results["results"].append(error_info)
            results["failed"] += 1
            
            if not continue_on_error:
                raise
    
    if not quiet:
        console.print(f"[green]Submitted {len(results['job_ids'])} jobs successfully[/green]")
        console.print("Use 'crawler status' to monitor job progress")
    
    return results


def _save_result(result: Dict[str, Any], url: str, index: int, output_dir: Path, output_format: str) -> None:
    """Save individual result to file."""
    try:
        # Create safe filename
        filename = _url_to_filename(url, index, output_format)
        output_file = output_dir / filename
        
        # Extract content based on result type
        if "results" in result:
            # Crawl result with multiple pages
            content = _format_crawl_result(result, output_format)
        else:
            # Single page result
            if output_format == "json":
                content = json.dumps(result, indent=2, default=str)
            else:
                content = result.get("content", "")
        
        output_file.write_text(content)
        
    except Exception as e:
        logger.error(f"Failed to save result for {url}: {e}")


def _format_crawl_result(result: Dict[str, Any], output_format: str) -> str:
    """Format crawl result for output."""
    if output_format == "json":
        return json.dumps(result, indent=2, default=str)
    
    # Markdown format for crawl results
    content = f"# Crawl Results for {result.get('url', 'Unknown')}\n\n"
    
    crawl_results = result.get("results", [])
    for i, page_result in enumerate(crawl_results):
        content += f"## Page {i + 1}: {page_result.get('url', 'Unknown')}\n\n"
        page_content = page_result.get("content", "")
        if page_content:
            content += page_content + "\n\n"
        else:
            content += "*No content extracted*\n\n"
    
    return content


def _handle_batch_results(
    results: Dict[str, Any],
    output_dir: Path,
    save_errors: bool,
    quiet: bool
) -> None:
    """Handle batch processing results."""
    if not quiet:
        _show_batch_summary(results)
    
    # Save summary
    summary_file = output_dir / "batch_summary.json"
    summary_file.write_text(json.dumps(results, indent=2, default=str))
    
    # Save errors if requested
    if save_errors and results.get("errors"):
        errors_file = output_dir / "batch_errors.json"
        errors_file.write_text(json.dumps(results["errors"], indent=2, default=str))
        
        if not quiet:
            console.print(f"[yellow]Errors saved to:[/yellow] {errors_file}")
    
    if not quiet:
        console.print(f"[green]Summary saved to:[/green] {summary_file}")


def _show_batch_summary(results: Dict[str, Any]) -> None:
    """Show batch processing summary."""
    table = Table(title="Batch Processing Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total URLs", str(results["total"]))
    table.add_row("Successful", str(results["successful"]))
    table.add_row("Failed", str(results["failed"]))
    
    if results["total"] > 0:
        success_rate = (results["successful"] / results["total"]) * 100
        table.add_row("Success Rate", f"{success_rate:.1f}%")
    
    if "job_ids" in results:
        table.add_row("Jobs Submitted", str(len(results["job_ids"])))
    
    console.print(table)


def _url_to_filename(url: str, index: int, output_format: str) -> str:
    """Convert URL to safe filename."""
    import re
    
    # Remove protocol
    filename = re.sub(r'^https?://', '', url)
    
    # Replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Replace multiple underscores with single
    filename = re.sub(r'_+', '_', filename)
    
    # Truncate if too long
    if len(filename) > 80:
        filename = filename[:80]
    
    # Remove trailing underscore and add index
    filename = filename.rstrip('_')
    filename = f"{index:03d}_{filename}"
    
    # Add extension
    ext = "json" if output_format == "json" else "md"
    filename += f".{ext}"
    
    return filename