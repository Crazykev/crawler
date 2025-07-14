"""Main CLI entry point for the Crawler system."""

import sys
import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.traceback import install

from ..foundation.config import get_config_manager
from ..foundation.logging import setup_logging, get_logger
from ..foundation.errors import handle_error, CrawlerError
from ..version import __version__
from .commands import scrape, crawl, batch, session, config, status

# Install rich traceback handler
install(show_locals=True)

# Create console for rich output
console = Console()


def setup_cli_logging(verbose: int) -> None:
    """Setup logging based on verbosity level.
    
    Args:
        verbose: Verbosity level (0-3)
    """
    level_map = {
        0: "WARNING",
        1: "INFO", 
        2: "DEBUG",
        3: "DEBUG"
    }
    
    log_level = level_map.get(verbose, "INFO")
    setup_logging(level=log_level)


def handle_cli_error(error: Exception, debug: bool = False) -> int:
    """Handle CLI errors with appropriate formatting.
    
    Args:
        error: Exception that occurred
        debug: Whether to show debug information
        
    Returns:
        Exit code
    """
    if isinstance(error, CrawlerError):
        # Handle known crawler errors
        console.print(f"[red]Error:[/red] {error.message}", style="red")
        if error.details:
            console.print(f"Details: {error.details}")
        return 1
    elif isinstance(error, click.ClickException):
        # Let click handle its own exceptions
        error.show()
        return error.exit_code
    else:
        # Handle unexpected errors
        if debug:
            console.print_exception()
        else:
            console.print(f"[red]Unexpected error:[/red] {str(error)}", style="red")
            console.print("Use --verbose for more details")
        return 1


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(),
    help="Configuration file path"
)
@click.option(
    "--verbose", 
    "-v", 
    count=True, 
    help="Increase verbosity (use -v, -vv, -vvv)"
)
@click.option(
    "--quiet", 
    "-q", 
    is_flag=True, 
    help="Suppress output except errors"
)
@click.option(
    "--no-color", 
    is_flag=True, 
    help="Disable colored output"
)
@click.version_option(version=__version__, prog_name="crawler")
@click.pass_context
def cli(ctx, config, verbose, quiet, no_color):
    """Crawler - A comprehensive web scraping and crawling solution.
    
    This tool provides powerful web scraping and crawling capabilities
    with support for single-page scraping, multi-page crawling, and
    batch operations.
    
    Examples:
    
        # Scrape a single page
        crawler scrape https://example.com
        
        # Crawl a website with depth limit
        crawler crawl https://example.com --max-depth 2
        
        # Batch process URLs from file
        crawler batch urls.txt
        
        # Manage browser sessions
        crawler session create --session-id my-session
        
        # Check system status
        crawler status
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Handle quiet mode
    if quiet:
        verbose = 0
    
    # Setup logging
    setup_cli_logging(verbose)
    
    # Store options in context
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet
    ctx.obj['no_color'] = no_color
    ctx.obj['config_path'] = config
    
    # Disable colors if requested
    if no_color:
        console._color_system = None
    
    # Initialize configuration if custom path provided
    if config:
        from pathlib import Path
        config_manager = get_config_manager()
        config_manager.config_path = Path(config)
        config_manager.reload_config()
        
        # Reset storage manager to pick up new configuration
        from ..core.storage import reset_storage_manager
        reset_storage_manager()


# Add command groups
cli.add_command(scrape)
cli.add_command(crawl)
cli.add_command(batch)
cli.add_command(session)
cli.add_command(config)
cli.add_command(status)


def main(args: Optional[list] = None, standalone_mode: bool = True) -> int:
    """Main entry point for the CLI.
    
    Args:
        args: Command line arguments (defaults to sys.argv)
        standalone_mode: Whether to run in standalone mode
        
    Returns:
        Exit code
    """
    try:
        if args is None:
            args = sys.argv[1:]
        
        # Run the CLI
        result = cli(args, standalone_mode=standalone_mode)
        
        # Handle different return types
        if isinstance(result, int):
            return result
        elif result is None:
            return 0
        else:
            return 0
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        return 130
    except Exception as e:
        debug = any('--verbose' in arg or '-v' in arg for arg in (args or []))
        return handle_cli_error(e, debug)


if __name__ == "__main__":
    sys.exit(main())