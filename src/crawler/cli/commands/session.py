"""CLI command for managing browser sessions."""

import asyncio
import json
from typing import Optional, Dict, Any

import click
from rich.console import Console
from rich.table import Table

from ...services import get_session_service, SessionConfig
from ...foundation.config import get_config_manager
from ...foundation.logging import get_logger
from ...foundation.errors import handle_error

console = Console()
logger = get_logger(__name__)


@click.group()
@click.pass_context
def session(ctx):
    """Manage browser sessions.
    
    Browser sessions allow you to maintain state across multiple
    scraping or crawling operations, including cookies, authentication,
    and other browser state.
    
    Examples:
    
        # Create a new session
        crawler session create --session-id my-session
        
        # List all sessions
        crawler session list
        
        # Show session details
        crawler session show my-session
        
        # Close a session
        crawler session close my-session
        
        # Clean up expired sessions
        crawler session cleanup
    """
    pass


@session.command()
@click.option(
    "--session-id",
    help="Custom session ID (auto-generated if not provided)"
)
@click.option(
    "--browser-type",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
    help="Browser type"
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode"
)
@click.option(
    "--timeout",
    type=int,
    default=30,
    help="Page load timeout in seconds"
)
@click.option(
    "--user-agent",
    help="Custom user agent string"
)
@click.option(
    "--proxy-url",
    help="Proxy URL"
)
@click.option(
    "--proxy-username",
    help="Proxy username"
)
@click.option(
    "--proxy-password",
    help="Proxy password"
)
@click.option(
    "--viewport-width",
    type=int,
    default=1920,
    help="Browser viewport width"
)
@click.option(
    "--viewport-height",
    type=int,
    default=1080,
    help="Browser viewport height"
)
@click.option(
    "--session-timeout",
    type=int,
    default=1800,
    help="Session timeout in seconds"
)
@click.pass_context
def create(ctx, session_id, browser_type, headless, timeout, user_agent,
           proxy_url, proxy_username, proxy_password, viewport_width,
           viewport_height, session_timeout):
    """Create a new browser session."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        # Prepare session configuration
        session_config = SessionConfig(
            browser_type=browser_type,
            headless=headless,
            timeout=timeout,
            user_agent=user_agent,
            proxy_url=proxy_url,
            proxy_username=proxy_username,
            proxy_password=proxy_password,
            viewport_width=viewport_width,
            viewport_height=viewport_height
        )
        
        # Create session
        result = asyncio.run(_create_session(
            session_config=session_config,
            session_id=session_id,
            timeout_seconds=session_timeout
        ))
        
        if not quiet:
            console.print(f"[green]Session created successfully![/green]")
            console.print(f"Session ID: {result['session_id']}")
            
            # Show session details
            table = Table(title="Session Configuration")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Session ID", result['session_id'])
            table.add_row("Browser Type", session_config.browser_type)
            table.add_row("Headless", "Yes" if session_config.headless else "No")
            table.add_row("Timeout", f"{session_config.timeout}s")
            table.add_row("Viewport", f"{session_config.viewport_width}x{session_config.viewport_height}")
            
            if session_config.user_agent:
                table.add_row("User Agent", session_config.user_agent)
            if session_config.proxy_url:
                table.add_row("Proxy URL", session_config.proxy_url)
            
            console.print(table)
        else:
            console.print(result['session_id'])
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to create session: {str(e)}")


@session.command()
@click.option(
    "--include-inactive",
    is_flag=True,
    help="Include inactive sessions in the list"
)
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format"
)
@click.pass_context
def list(ctx, include_inactive, format):
    """List browser sessions."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        sessions = asyncio.run(_list_sessions(include_inactive))
        
        if format == "json":
            console.print(json.dumps(sessions, indent=2, default=str))
        else:
            if not sessions:
                if not quiet:
                    console.print("[yellow]No sessions found.[/yellow]")
                return
            
            table = Table(title="Browser Sessions")
            table.add_column("Session ID", style="cyan")
            table.add_column("Browser", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Created", style="blue")
            table.add_column("Last Accessed", style="blue")
            table.add_column("Pages", style="magenta")
            
            for session in sessions:
                status = "Active" if session.get("is_active", False) else "Inactive"
                table.add_row(
                    session["session_id"],
                    session["config"]["browser_type"],
                    status,
                    session["created_at"][:19],  # Remove microseconds
                    session["last_accessed"][:19],
                    str(session.get("page_count", 0))
                )
            
            console.print(table)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to list sessions: {str(e)}")


@session.command()
@click.argument("session_id")
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format"
)
@click.pass_context
def show(ctx, session_id, format):
    """Show details of a specific session."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        session = asyncio.run(_get_session(session_id))
        
        if not session:
            raise click.ClickException(f"Session {session_id} not found")
        
        if format == "json":
            console.print(json.dumps(session, indent=2, default=str))
        else:
            table = Table(title=f"Session Details: {session_id}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Session ID", session["session_id"])
            table.add_row("Status", "Active" if session.get("is_active", False) else "Inactive")
            table.add_row("Created", session["created_at"])
            table.add_row("Last Accessed", session["last_accessed"])
            table.add_row("Page Count", str(session.get("page_count", 0)))
            
            # Configuration details
            config = session.get("config", {})
            table.add_row("Browser Type", config.get("browser_type", "Unknown"))
            table.add_row("Headless", "Yes" if config.get("headless", True) else "No")
            table.add_row("Timeout", f"{config.get('timeout', 30)}s")
            table.add_row("Viewport", f"{config.get('viewport_width', 1920)}x{config.get('viewport_height', 1080)}")
            
            if config.get("user_agent"):
                table.add_row("User Agent", config["user_agent"])
            if config.get("proxy_url"):
                table.add_row("Proxy URL", config["proxy_url"])
            
            # State data
            state_data = session.get("state_data", {})
            if state_data:
                table.add_row("State Data", json.dumps(state_data, indent=2))
            
            console.print(table)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to show session: {str(e)}")


@session.command()
@click.argument("session_id")
@click.pass_context
def close(ctx, session_id):
    """Close a browser session."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        success = asyncio.run(_close_session(session_id))
        
        if success:
            if not quiet:
                console.print(f"[green]Session {session_id} closed successfully.[/green]")
            else:
                console.print("OK")
        else:
            if not quiet:
                console.print(f"[yellow]Session {session_id} not found or already closed.[/yellow]")
            else:
                console.print("NOT_FOUND")
                
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to close session: {str(e)}")


@session.command()
@click.pass_context
def cleanup(ctx):
    """Clean up expired sessions."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        count = asyncio.run(_cleanup_expired_sessions())
        
        if not quiet:
            if count > 0:
                console.print(f"[green]Cleaned up {count} expired sessions.[/green]")
            else:
                console.print("[blue]No expired sessions found.[/blue]")
        else:
            console.print(count)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to cleanup sessions: {str(e)}")


@session.command()
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format"
)
@click.pass_context
def stats(ctx, format):
    """Show session statistics."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        statistics = asyncio.run(_get_session_statistics())
        
        if format == "json":
            console.print(json.dumps(statistics, indent=2, default=str))
        else:
            if "error" in statistics:
                console.print(f"[red]Error getting statistics:[/red] {statistics['error']}")
                return
            
            # Summary table
            table = Table(title="Session Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Active", str(statistics.get("total_active", 0)))
            table.add_row("Total Created", str(statistics.get("total_created", 0)))
            table.add_row("Total Closed", str(statistics.get("total_closed", 0)))
            
            console.print(table)
            
            # Detailed session information
            session_details = statistics.get("session_details", [])
            if session_details:
                details_table = Table(title="Active Sessions Details")
                details_table.add_column("Session ID", style="cyan")
                details_table.add_column("Age", style="green")
                details_table.add_column("Idle Time", style="yellow")
                details_table.add_column("Pages", style="magenta")
                details_table.add_column("Browser", style="blue")
                details_table.add_column("Status", style="red")
                
                for detail in session_details:
                    age_str = f"{detail['age_seconds']:.0f}s"
                    idle_str = f"{detail['idle_seconds']:.0f}s"
                    status = "Expired" if detail.get("is_expired", False) else "Active"
                    
                    details_table.add_row(
                        detail["session_id"],
                        age_str,
                        idle_str,
                        str(detail.get("page_count", 0)),
                        detail.get("config", {}).get("browser_type", "Unknown"),
                        status
                    )
                
                console.print(details_table)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to get session statistics: {str(e)}")


# Helper functions

async def _create_session(
    session_config: SessionConfig,
    session_id: Optional[str],
    timeout_seconds: int
) -> Dict[str, Any]:
    """Create a new browser session."""
    session_service = get_session_service()
    await session_service.initialize()
    
    created_session_id = await session_service.create_session(
        session_config=session_config,
        session_id=session_id,
        timeout_seconds=timeout_seconds
    )
    
    return {
        "session_id": created_session_id,
        "config": session_config.to_dict()
    }


async def _list_sessions(include_inactive: bool) -> list:
    """List all browser sessions."""
    session_service = get_session_service()
    await session_service.initialize()
    
    return await session_service.list_sessions(include_inactive=include_inactive)


async def _get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific session."""
    session_service = get_session_service()
    await session_service.initialize()
    
    session = await session_service.get_session(session_id)
    return session.to_dict() if session else None


async def _close_session(session_id: str) -> bool:
    """Close a browser session."""
    session_service = get_session_service()
    await session_service.initialize()
    
    return await session_service.close_session(session_id)


async def _cleanup_expired_sessions() -> int:
    """Clean up expired sessions."""
    session_service = get_session_service()
    await session_service.initialize()
    
    return await session_service.cleanup_expired_sessions()


async def _get_session_statistics() -> Dict[str, Any]:
    """Get session statistics."""
    session_service = get_session_service()
    await session_service.initialize()
    
    return await session_service.get_session_statistics()