"""CLI command for system status monitoring."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.progress import Progress, BarColumn, TextColumn

from ...core import get_job_manager, get_storage_manager
from ...services import get_session_service, get_scrape_service, get_crawl_service
from ...foundation.config import get_config_manager
from ...foundation.metrics import get_metrics_collector
from ...foundation.logging import get_logger
from ...foundation.errors import handle_error

console = Console()
logger = get_logger(__name__)


@click.group()
@click.pass_context
def status(ctx):
    """Show system status and monitoring information.
    
    Displays information about job queues, active sessions, system metrics,
    recent activity, and error summaries.
    
    Examples:
    
        # Show overall system status
        crawler status
        
        # Show job queue status
        crawler status jobs
        
        # Show session status
        crawler status sessions
        
        # Show system metrics
        crawler status metrics
        
        # Monitor status in real-time
        crawler status monitor --interval 5
    """
    pass


@status.command(name="overview")
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format"
)
@click.pass_context
def overview(ctx, format):
    """Show overall system status."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        status_data = asyncio.run(_get_system_overview())
        
        if format == "json":
            console.print(json.dumps(status_data, indent=2, default=str))
        else:
            _display_system_overview(status_data, quiet)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to get system status: {str(e)}")


@status.command()
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format"
)
@click.option(
    "--limit",
    type=int,
    default=10,
    help="Number of jobs to show"
)
@click.pass_context
def jobs(ctx, format, limit):
    """Show job queue status."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        job_data = asyncio.run(_get_job_status(limit))
        
        if format == "json":
            console.print(json.dumps(job_data, indent=2, default=str))
        else:
            _display_job_status(job_data, quiet)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to get job status: {str(e)}")


@status.command()
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format"
)
@click.pass_context
def sessions(ctx, format):
    """Show session status."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        session_data = asyncio.run(_get_session_status())
        
        if format == "json":
            console.print(json.dumps(session_data, indent=2, default=str))
        else:
            _display_session_status(session_data, quiet)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to get session status: {str(e)}")


@status.command()
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format"
)
@click.pass_context
def metrics(ctx, format):
    """Show system metrics."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        metrics_data = asyncio.run(_get_metrics_status())
        
        if format == "json":
            console.print(json.dumps(metrics_data, indent=2, default=str))
        else:
            _display_metrics_status(metrics_data, quiet)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to get metrics: {str(e)}")


@status.command()
@click.option(
    "--interval",
    type=int,
    default=5,
    help="Update interval in seconds"
)
@click.option(
    "--count",
    type=int,
    help="Number of updates (default: unlimited)"
)
@click.pass_context
def monitor(ctx, interval, count):
    """Monitor system status in real-time."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        asyncio.run(_monitor_system_status(interval, count, quiet))
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user.[/yellow]")
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to monitor status: {str(e)}")


@status.command()
@click.argument("job_id")
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format"
)
@click.pass_context
def job(ctx, job_id, format):
    """Show specific job status."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        job_data = asyncio.run(_get_specific_job_status(job_id))
        
        if not job_data:
            raise click.ClickException(f"Job {job_id} not found")
        
        if format == "json":
            console.print(json.dumps(job_data, indent=2, default=str))
        else:
            _display_specific_job_status(job_data, quiet)
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to get job status: {str(e)}")


# Helper functions

async def _get_system_overview() -> Dict[str, Any]:
    """Get overall system status."""
    overview = {
        "timestamp": datetime.utcnow().isoformat(),
        "jobs": {},
        "sessions": {},
        "metrics": {},
        "storage": {},
        "services": {}
    }
    
    try:
        # Job manager status
        job_manager = get_job_manager()
        await job_manager.initialize()
        job_stats = await job_manager.get_queue_statistics()
        overview["jobs"] = job_stats
        
    except Exception as e:
        overview["jobs"] = {"error": str(e)}
    
    try:
        # Session status
        session_service = get_session_service()
        await session_service.initialize()
        session_stats = await session_service.get_session_statistics()
        overview["sessions"] = session_stats
        
    except Exception as e:
        overview["sessions"] = {"error": str(e)}
    
    try:
        # Metrics
        metrics_collector = get_metrics_collector()
        metrics_summary = await metrics_collector.get_summary()
        overview["metrics"] = metrics_summary
        
    except Exception as e:
        overview["metrics"] = {"error": str(e)}
    
    try:
        # Storage status
        storage_manager = get_storage_manager()
        await storage_manager.initialize()
        storage_stats = await storage_manager.get_storage_statistics()
        overview["storage"] = storage_stats
        
    except Exception as e:
        overview["storage"] = {"error": str(e)}
    
    # Service status
    overview["services"] = {
        "scrape_service": "initialized",
        "crawl_service": "initialized",
        "session_service": "initialized"
    }
    
    return overview


async def _get_job_status(limit: int) -> Dict[str, Any]:
    """Get job queue status."""
    job_manager = get_job_manager()
    await job_manager.initialize()
    
    # Get queue statistics
    stats = await job_manager.get_queue_statistics()
    
    # Get recent jobs
    recent_jobs = await job_manager.get_recent_jobs(limit)
    
    return {
        "statistics": stats,
        "recent_jobs": recent_jobs,
        "timestamp": datetime.utcnow().isoformat()
    }


async def _get_session_status() -> Dict[str, Any]:
    """Get session status."""
    session_service = get_session_service()
    await session_service.initialize()
    
    stats = await session_service.get_session_statistics()
    sessions = await session_service.list_sessions(include_inactive=False)
    
    return {
        "statistics": stats,
        "active_sessions": sessions,
        "timestamp": datetime.utcnow().isoformat()
    }


async def _get_metrics_status() -> Dict[str, Any]:
    """Get metrics status."""
    metrics_collector = get_metrics_collector()
    
    summary = await metrics_collector.get_summary()
    recent_metrics = await metrics_collector.get_recent_metrics(limit=100)
    
    return {
        "summary": summary,
        "recent_metrics": recent_metrics,
        "timestamp": datetime.utcnow().isoformat()
    }


async def _get_specific_job_status(job_id: str) -> Dict[str, Any]:
    """Get status of specific job."""
    job_manager = get_job_manager()
    await job_manager.initialize()
    
    job_info = await job_manager.get_job_status(job_id)
    return job_info


async def _monitor_system_status(interval: int, count: int, quiet: bool) -> None:
    """Monitor system status in real-time."""
    updates = 0
    
    while True:
        if count and updates >= count:
            break
        
        # Clear screen
        console.clear()
        
        # Get status
        status_data = await _get_system_overview()
        
        # Display
        _display_system_overview(status_data, quiet)
        
        # Show update info
        now = datetime.now().strftime("%H:%M:%S")
        console.print(f"\n[dim]Last updated: {now} | Press Ctrl+C to stop[/dim]")
        
        updates += 1
        
        # Wait for next update
        if count is None or updates < count:
            await asyncio.sleep(interval)


def _display_system_overview(data: Dict[str, Any], quiet: bool) -> None:
    """Display system overview."""
    if quiet:
        # Minimal output for quiet mode
        jobs = data.get("jobs", {})
        sessions = data.get("sessions", {})
        
        console.print(f"Jobs: {jobs.get('total_pending', 0)} pending, {jobs.get('total_running', 0)} running")
        console.print(f"Sessions: {sessions.get('total_active', 0)} active")
        return
    
    # Rich display for normal mode
    console.print(Panel.fit("[bold green]System Status Overview[/bold green]", border_style="green"))
    
    # Create panels for different sections
    panels = []
    
    # Jobs panel
    jobs = data.get("jobs", {})
    if "error" in jobs:
        job_content = f"[red]Error: {jobs['error']}[/red]"
    else:
        job_content = f"""
[green]Pending:[/green] {jobs.get('total_pending', 0)}
[yellow]Running:[/yellow] {jobs.get('total_running', 0)}
[blue]Completed:[/blue] {jobs.get('total_completed', 0)}
[red]Failed:[/red] {jobs.get('total_failed', 0)}
"""
    panels.append(Panel(job_content, title="Job Queue", border_style="blue"))
    
    # Sessions panel
    sessions = data.get("sessions", {})
    if "error" in sessions:
        session_content = f"[red]Error: {sessions['error']}[/red]"
    else:
        session_content = f"""
[green]Active:[/green] {sessions.get('total_active', 0)}
[blue]Total Created:[/blue] {sessions.get('total_created', 0)}
[red]Total Closed:[/red] {sessions.get('total_closed', 0)}
"""
    panels.append(Panel(session_content, title="Sessions", border_style="yellow"))
    
    # Storage panel
    storage = data.get("storage", {})
    if "error" in storage:
        storage_content = f"[red]Error: {storage['error']}[/red]"
    else:
        storage_content = f"""
[green]Database:[/green] Connected
[blue]Cache Entries:[/blue] {storage.get('cache_entries', 0)}
[yellow]Results:[/yellow] {storage.get('total_results', 0)}
"""
    panels.append(Panel(storage_content, title="Storage", border_style="cyan"))
    
    # Display panels in columns
    console.print(Columns(panels, equal=True))
    
    # Services status
    services = data.get("services", {})
    service_table = Table(title="Service Status")
    service_table.add_column("Service", style="cyan")
    service_table.add_column("Status", style="green")
    
    for service, status in services.items():
        service_table.add_row(service.replace("_", " ").title(), status.title())
    
    console.print(service_table)


def _display_job_status(data: Dict[str, Any], quiet: bool) -> None:
    """Display job status."""
    if quiet:
        stats = data.get("statistics", {})
        console.print(f"Pending: {stats.get('total_pending', 0)}, Running: {stats.get('total_running', 0)}")
        return
    
    stats = data.get("statistics", {})
    recent_jobs = data.get("recent_jobs", [])
    
    # Statistics table
    stats_table = Table(title="Job Queue Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")
    
    stats_table.add_row("Total Pending", str(stats.get("total_pending", 0)))
    stats_table.add_row("Total Running", str(stats.get("total_running", 0)))
    stats_table.add_row("Total Completed", str(stats.get("total_completed", 0)))
    stats_table.add_row("Total Failed", str(stats.get("total_failed", 0)))
    
    console.print(stats_table)
    
    # Recent jobs table
    if recent_jobs:
        jobs_table = Table(title="Recent Jobs")
        jobs_table.add_column("Job ID", style="cyan")
        jobs_table.add_column("Type", style="green")
        jobs_table.add_column("Status", style="yellow")
        jobs_table.add_column("Created", style="blue")
        jobs_table.add_column("Progress", style="magenta")
        
        for job in recent_jobs:
            status = job.get("status", "unknown")
            if status == "completed":
                status = "[green]completed[/green]"
            elif status == "failed":
                status = "[red]failed[/red]"
            elif status == "running":
                status = "[yellow]running[/yellow]"
            
            jobs_table.add_row(
                job.get("job_id", "")[:8] + "...",
                job.get("job_type", ""),
                status,
                job.get("created_at", "")[:19],
                f"{job.get('progress', 0)}%"
            )
        
        console.print(jobs_table)


def _display_session_status(data: Dict[str, Any], quiet: bool) -> None:
    """Display session status."""
    if quiet:
        stats = data.get("statistics", {})
        console.print(f"Active: {stats.get('total_active', 0)}")
        return
    
    stats = data.get("statistics", {})
    sessions = data.get("active_sessions", [])
    
    # Statistics
    stats_table = Table(title="Session Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")
    
    stats_table.add_row("Total Active", str(stats.get("total_active", 0)))
    stats_table.add_row("Total Created", str(stats.get("total_created", 0)))
    stats_table.add_row("Total Closed", str(stats.get("total_closed", 0)))
    
    console.print(stats_table)
    
    # Active sessions
    if sessions:
        session_table = Table(title="Active Sessions")
        session_table.add_column("Session ID", style="cyan")
        session_table.add_column("Browser", style="green")
        session_table.add_column("Created", style="blue")
        session_table.add_column("Pages", style="magenta")
        
        for session in sessions:
            session_table.add_row(
                session.get("session_id", "")[:8] + "...",
                session.get("config", {}).get("browser_type", "unknown"),
                session.get("created_at", "")[:19],
                str(session.get("page_count", 0))
            )
        
        console.print(session_table)


def _display_metrics_status(data: Dict[str, Any], quiet: bool) -> None:
    """Display metrics status."""
    if quiet:
        summary = data.get("summary", {})
        console.print(f"Metrics: {len(summary)} collected")
        return
    
    summary = data.get("summary", {})
    
    if not summary:
        console.print("[yellow]No metrics data available.[/yellow]")
        return
    
    # Metrics summary
    metrics_table = Table(title="System Metrics Summary")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="green")
    
    for metric_name, metric_value in summary.items():
        if isinstance(metric_value, (int, float)):
            if isinstance(metric_value, float):
                formatted_value = f"{metric_value:.2f}"
            else:
                formatted_value = str(metric_value)
        else:
            formatted_value = str(metric_value)
        
        metrics_table.add_row(metric_name.replace("_", " ").title(), formatted_value)
    
    console.print(metrics_table)


def _display_specific_job_status(data: Dict[str, Any], quiet: bool) -> None:
    """Display specific job status."""
    if quiet:
        console.print(data.get("status", "unknown"))
        return
    
    # Job details table
    table = Table(title=f"Job Details: {data.get('job_id', 'Unknown')}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Job ID", data.get("job_id", "Unknown"))
    table.add_row("Type", data.get("job_type", "Unknown"))
    table.add_row("Status", data.get("status", "Unknown"))
    table.add_row("Priority", str(data.get("priority", 0)))
    table.add_row("Created", data.get("created_at", "Unknown"))
    table.add_row("Progress", f"{data.get('progress', 0)}%")
    
    if data.get("error_message"):
        table.add_row("Error", data["error_message"])
    
    console.print(table)