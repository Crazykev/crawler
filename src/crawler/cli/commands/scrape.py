"""CLI command for scraping single pages."""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from ...services import get_scrape_service
from ...foundation.config import get_config_manager
from ...foundation.logging import get_logger
from ...foundation.errors import handle_error

console = Console()
logger = get_logger(__name__)


@click.command()
@click.argument("url")
@click.option(
    "--output", 
    "-o", 
    type=click.Path(), 
    help="Output file path"
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
    help="Take screenshot of the page"
)
@click.option(
    "--pdf",
    is_flag=True,
    help="Generate PDF of the page"
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
@click.pass_context
def scrape(ctx, url, output, output_format, extract_strategy, css_selector, 
          llm_model, llm_prompt, timeout, headless, user_agent, session_id,
          js_code, wait_for, screenshot, pdf, cache, cache_ttl, async_job, priority):
    """Scrape a single webpage.
    
    Extracts content from a single webpage using various strategies
    and outputs in multiple formats.
    
    Examples:
    
        # Basic scraping
        crawler scrape https://example.com
        
        # Scrape with CSS extraction
        crawler scrape https://example.com --extract-strategy css --css-selector ".content"
        
        # Scrape with LLM extraction
        crawler scrape https://example.com --extract-strategy llm --llm-model openai/gpt-4
        
        # Save to file
        crawler scrape https://example.com --output result.json --format json
        
        # Run as async job
        crawler scrape https://example.com --async-job
    """
    verbose = ctx.obj.get('verbose', 0) if ctx.obj else 0
    quiet = ctx.obj.get('quiet', False) if ctx.obj else False
    
    try:
        # Prepare options
        options = _prepare_scrape_options(
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
        
        # Run scraping
        if async_job:
            result = asyncio.run(_run_async_scrape(
                url=url,
                options=options,
                extraction_strategy=extraction_strategy,
                output_format=output_format,
                session_id=session_id,
                priority=priority,
                quiet=quiet
            ))
        else:
            result = asyncio.run(_run_sync_scrape(
                url=url,
                options=options,
                extraction_strategy=extraction_strategy,
                output_format=output_format,
                session_id=session_id,
                quiet=quiet
            ))
        
        # Handle output
        _handle_output(result, output, output_format, quiet, async_job)
        
    except Exception as e:
        handle_error(e)
        if verbose > 0:
            console.print_exception()
        console.print(f"[red]Error:[/red] {str(e)}")
        ctx.exit(1)


def _prepare_scrape_options(
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
    """Prepare scraping options."""
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


async def _run_sync_scrape(
    url: str,
    options: Dict[str, Any],
    extraction_strategy: Optional[Dict[str, Any]],
    output_format: str,
    session_id: Optional[str],
    quiet: bool
) -> Dict[str, Any]:
    """Run synchronous scraping."""
    scrape_service = get_scrape_service()
    await scrape_service.initialize()
    
    if not quiet:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task(f"Scraping {url}...", total=None)
            
            result = await scrape_service.scrape_single(
                url=url,
                options=options,
                extraction_strategy=extraction_strategy,
                output_format=output_format,
                session_id=session_id
            )
            
            progress.update(task, completed=True)
    else:
        result = await scrape_service.scrape_single(
            url=url,
            options=options,
            extraction_strategy=extraction_strategy,
            output_format=output_format,
            session_id=session_id
        )
    
    return result


async def _run_async_scrape(
    url: str,
    options: Dict[str, Any],
    extraction_strategy: Optional[Dict[str, Any]],
    output_format: str,
    session_id: Optional[str],
    priority: int,
    quiet: bool
) -> str:
    """Run asynchronous scraping."""
    scrape_service = get_scrape_service()
    await scrape_service.initialize()
    
    if not quiet:
        console.print(f"Submitting scrape job for {url}...")
    
    job_id = await scrape_service.scrape_single_async(
        url=url,
        options=options,
        extraction_strategy=extraction_strategy,
        output_format=output_format,
        session_id=session_id,
        priority=priority
    )
    
    return job_id


def _handle_output(
    result: Any,
    output_path: Optional[str],
    output_format: str,
    quiet: bool,
    async_job: bool
) -> None:
    """Handle output formatting and saving."""
    if async_job:
        # Result is job ID
        if not quiet:
            console.print(f"[green]Job submitted successfully![/green]")
            console.print(f"Job ID: {result}")
            console.print("Use 'crawler status' to check job status")
        else:
            console.print(result)
        return
    
    # Result is scrape data
    if not result.get("success"):
        error_msg = result.get("error", "Unknown error")
        console.print(f"[red]Scraping failed:[/red] {error_msg}")
        from ...foundation.errors import ValidationError
        raise ValidationError(f"Scraping failed: {error_msg}")
    
    # Format output based on type
    if output_format == "json":
        output_content = json.dumps(result, indent=2, default=str)
    else:
        output_content = result.get("content", "")
    
    # Save to file or print to console
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(output_content)
        
        if not quiet:
            console.print(f"[green]Output saved to:[/green] {output_path}")
    else:
        if not quiet:
            # Show summary table
            _show_scrape_summary(result)
            console.print("\n[bold]Content:[/bold]")
        
        console.print(output_content)


def _show_scrape_summary(result: Dict[str, Any]) -> None:
    """Show scraping summary table."""
    table = Table(title="Scrape Summary")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("URL", result.get("url", "N/A"))
    table.add_row("Title", result.get("title", "N/A"))
    table.add_row("Status Code", str(result.get("status_code", "N/A")))
    table.add_row("Success", "✓" if result.get("success") else "✗")
    
    metadata = result.get("metadata", {})
    if metadata:
        table.add_row("Load Time", f"{metadata.get('load_time', 0):.2f}s")
        table.add_row("Content Size", f"{metadata.get('size', 0)} bytes")
        table.add_row("Format", metadata.get("output_format", "N/A"))
    
    links_count = len(result.get("links", []))
    images_count = len(result.get("images", []))
    table.add_row("Links Found", str(links_count))
    table.add_row("Images Found", str(images_count))
    
    console.print(table)