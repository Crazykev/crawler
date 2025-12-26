"""CLI command for managing configuration."""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from ...foundation.config import get_config_manager
from ...foundation.logging import get_logger
from ...foundation.errors import handle_error

console = Console()
logger = get_logger(__name__)


@click.group()
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(),
    help="Configuration file path"
)
@click.pass_context
def config(ctx, config_path):
    """Manage crawler configuration.
    
    The crawler uses a hierarchical configuration system that supports
    YAML files, environment variables, and command-line overrides.
    
    Examples:
    
        # Show current configuration
        crawler config show
        
        # Get a specific setting
        crawler config get scrape.timeout
        
        # Set a setting
        crawler config set scrape.timeout 45
        
        # Initialize default configuration
        crawler config init
        
        # Validate configuration
        crawler config validate
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Store config path in context for subcommands
    if config_path:
        ctx.obj['config_path'] = config_path


@config.command()
@click.option(
    "--format",
    type=click.Choice(["yaml", "json", "table"]),
    default="table",
    show_default=True,
    help="Output format"
)
@click.option(
    "--section",
    help="Show only specific configuration section"
)
@click.pass_context
def show(ctx, format, section):
    """Show current configuration."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        config_manager = get_config_manager()
        
        if section:
            # Show specific section
            config_data = config_manager.get_section(section)
            if config_data is None:
                raise click.ClickException(f"Configuration section '{section}' not found")
        else:
            # Show all configuration
            config_data = config_manager.get_all_settings()
        
        if format == "json":
            console.print(json.dumps(config_data, indent=2, default=str))
        elif format == "yaml":
            console.print(yaml.dump(config_data, default_flow_style=False))
        else:
            # Table format
            if section:
                _show_config_section(section, config_data)
            else:
                _show_config_tree(config_data)
                
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to show configuration: {str(e)}")


@config.command()
@click.argument("key")
@click.option(
    "--format",
    type=click.Choice(["yaml", "json", "raw"]),
    default="raw",
    show_default=True,
    help="Output format"
)
@click.pass_context
def get(ctx, key, format):
    """Get a specific configuration value."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        config_path = ctx.obj.get('config_path') if ctx.obj else None
        if config_path:
            from ...foundation.config import ConfigManager
            config_manager = ConfigManager(config_path)
            # Make sure to load the config from file
            config_manager.load_from_file()
        else:
            config_manager = get_config_manager()
        value = config_manager.get_setting(key)
        
        if value is None:
            raise click.ClickException(f"Configuration key '{key}' not found")
        
        if format == "json":
            console.print(json.dumps(value, indent=2, default=str))
        elif format == "yaml":
            console.print(yaml.dump({key: value}, default_flow_style=False))
        else:
            # Raw format
            if isinstance(value, (dict, list)):
                console.print(json.dumps(value, default=str))
            else:
                console.print(str(value))
                
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to get configuration: {str(e)}")


@config.command()
@click.argument("key")
@click.argument("value")
@click.option(
    "--type",
    "value_type",
    type=click.Choice(["string", "int", "float", "bool", "json"]),
    default="string",
    show_default=True,
    help="Value type"
)
@click.option(
    "--persistent",
    is_flag=True,
    help="Save to configuration file"
)
@click.pass_context
def set(ctx, key, value, value_type, persistent):
    """Set a configuration value."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        config_path = ctx.obj.get('config_path') if ctx.obj else None
        if config_path:
            from ...foundation.config import ConfigManager
            config_manager = ConfigManager(config_path)
            # Load existing config if file exists
            if Path(config_path).exists():
                config_manager.load_from_file()
        else:
            config_manager = get_config_manager()
        
        # Auto-detect type for known settings if type is default (string)
        if value_type == "string":
            detected_type = _auto_detect_type(key, value)
            if detected_type != "string":
                value_type = detected_type
        
        # Convert value to appropriate type
        converted_value = _convert_value(value, value_type)
        
        # Set the value
        config_manager.set_setting(key, converted_value)
        
        if persistent or config_path:
            # Save to file (always save if using custom config path)
            config_manager.save_to_file()
            if not quiet:
                console.print(f"[green]Configuration saved to file.[/green]")
        
        if not quiet:
            console.print(f"[green]Set {key} = {converted_value}[/green]")
        else:
            console.print("OK")
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to set configuration: {str(e)}")


@config.command()
@click.option(
    "--config-path",
    type=click.Path(),
    help="Configuration file path (default: ~/.crawler/config.yaml)"
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing configuration file"
)
@click.pass_context
def init(ctx, config_path, force):
    """Initialize default configuration."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        config_manager = get_config_manager()
        
        # Determine config file path
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = config_manager.get_default_config_path()
        
        # Check if file exists
        if config_file.exists() and not force:
            raise click.ClickException(f"Configuration file already exists: {config_file}. Use --force to overwrite.")
        
        # Create directory if needed
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate default configuration
        default_config = _get_default_config()
        
        # Write to file
        with open(config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
        
        if not quiet:
            console.print(f"[green]Default configuration created:[/green] {config_file}")
            console.print("You can now edit the configuration file or use 'crawler config set' to modify settings.")
        else:
            console.print(str(config_file))
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to initialize configuration: {str(e)}")


@config.command()
@click.option(
    "--config-path",
    type=click.Path(exists=True),
    help="Configuration file to validate"
)
@click.pass_context
def validate(ctx, config_path):
    """Validate configuration."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        config_manager = get_config_manager()
        
        if config_path:
            # Validate specific file
            config_file = Path(config_path)
            validation_result = config_manager.validate_config_file(config_file)
        else:
            # Validate current configuration
            validation_result = config_manager.validate_current_config()
        
        if validation_result["valid"]:
            if not quiet:
                console.print("[green]Configuration is valid.[/green]")
            else:
                console.print("OK")
        else:
            if not quiet:
                console.print("[red]Configuration validation failed:[/red]")
                for error in validation_result["errors"]:
                    console.print(f"  - {error}")
            else:
                console.print("INVALID")
                
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to validate configuration: {str(e)}")


@config.command()
@click.pass_context
def path(ctx):
    """Show configuration file paths."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        config_manager = get_config_manager()
        
        if not quiet:
            table = Table(title="Configuration Paths")
            table.add_column("Type", style="cyan")
            table.add_column("Path", style="green")
            table.add_column("Exists", style="yellow")
            
            # Current config file
            current_path = config_manager.config_path
            if current_path:
                table.add_row("Current", str(current_path), "Yes" if current_path.exists() else "No")
            
            # Default config file
            default_path = config_manager.get_default_config_path()
            table.add_row("Default", str(default_path), "Yes" if default_path.exists() else "No")
            
            # System config file
            system_path = config_manager.get_system_config_path()
            table.add_row("System", str(system_path), "Yes" if system_path.exists() else "No")
            
            console.print(table)
        else:
            # Just print current config path
            current_path = config_manager.config_path
            if current_path:
                console.print(str(current_path))
            else:
                console.print(str(config_manager.get_default_config_path()))
                
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to show configuration paths: {str(e)}")


@config.command()
@click.argument("output_file", type=click.Path())
@click.option(
    "--format",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    show_default=True,
    help="Export format"
)
@click.pass_context
def export(ctx, output_file, format):
    """Export configuration to file."""
    quiet = ctx.obj.get('quiet', False)
    
    try:
        config_manager = get_config_manager()
        config_data = config_manager.get_all_settings()
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with open(output_path, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
        else:
            with open(output_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
        
        if not quiet:
            console.print(f"[green]Configuration exported to:[/green] {output_path}")
        else:
            console.print("OK")
            
    except Exception as e:
        handle_error(e)
        raise click.ClickException(f"Failed to export configuration: {str(e)}")


# Helper functions

def _auto_detect_type(key: str, value: str) -> str:
    """Auto-detect the appropriate type for a configuration key."""
    # Known integer settings
    integer_keys = {
        "timeout", "max_depth", "max_pages", "max_duration", "concurrent_requests",
        "cache_ttl", "session_timeout", "retention_days", "cache_size",
        "viewport_width", "viewport_height", "retry_attempts", "max_concurrent",
        "collection_interval", "port"
    }
    
    # Known float settings
    float_keys = {"delay"}
    
    # Known boolean settings
    boolean_keys = {
        "headless", "cache_enabled", "respect_robots", "allow_external_links",
        "allow_subdomains", "enabled", "wal_mode", "create_index", "compress_results"
    }
    
    # Check if the key (or last part of dotted key) matches known patterns
    key_parts = key.split(".")
    last_key = key_parts[-1]
    
    if last_key in boolean_keys or any(k in key.lower() for k in ["enabled", "headless"]):
        return "bool"
    elif last_key in integer_keys or any(k in key.lower() for k in ["timeout", "max_", "count", "size", "port"]):
        # Also try to parse as int to confirm
        try:
            int(value)
            return "int"
        except ValueError:
            pass
    elif last_key in float_keys or "delay" in key.lower():
        try:
            float(value)
            return "float"
        except ValueError:
            pass
    
    # Fallback: try to detect by value format
    if value.lower() in ("true", "false", "yes", "no", "on", "off", "1", "0"):
        return "bool"
    
    try:
        int(value)
        return "int"
    except ValueError:
        pass
    
    try:
        float(value)
        return "float"
    except ValueError:
        pass
    
    return "string"


def _convert_value(value: str, value_type: str) -> Any:
    """Convert string value to appropriate type."""
    if value_type == "string":
        return value
    elif value_type == "int":
        return int(value)
    elif value_type == "float":
        return float(value)
    elif value_type == "bool":
        return value.lower() in ("true", "yes", "1", "on")
    elif value_type == "json":
        return json.loads(value)
    else:
        return value


def _show_config_tree(config_data: Dict[str, Any]) -> None:
    """Show configuration as a tree structure."""
    tree = Tree("Configuration")
    
    def add_dict_to_tree(parent_node, data, level=0):
        for key, value in data.items():
            if isinstance(value, dict):
                section_node = parent_node.add(f"[bold cyan]{key}[/bold cyan]")
                add_dict_to_tree(section_node, value, level + 1)
            else:
                # Format value based on type
                if isinstance(value, str):
                    formatted_value = f'"{value}"'
                elif isinstance(value, bool):
                    formatted_value = f"[green]{value}[/green]"
                elif isinstance(value, (int, float)):
                    formatted_value = f"[yellow]{value}[/yellow]"
                else:
                    formatted_value = str(value)
                
                parent_node.add(f"{key}: {formatted_value}")
    
    add_dict_to_tree(tree, config_data)
    console.print(tree)


def _show_config_section(section_name: str, config_data: Dict[str, Any]) -> None:
    """Show a specific configuration section as a table."""
    table = Table(title=f"Configuration Section: {section_name}")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Type", style="yellow")
    
    def add_dict_to_table(data, prefix=""):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                add_dict_to_table(value, full_key)
            else:
                value_str = json.dumps(value) if isinstance(value, (list, dict)) else str(value)
                type_str = type(value).__name__
                table.add_row(full_key, value_str, type_str)
    
    add_dict_to_table(config_data)
    console.print(table)


def _get_default_config() -> Dict[str, Any]:
    """Get default configuration structure."""
    return {
        "scrape": {
            "timeout": 30,
            "headless": True,
            "user_agent": "Crawler/1.0",
            "cache_enabled": True,
            "cache_ttl": 3600,
        },
        "crawl": {
            "max_depth": 3,
            "max_pages": 100,
            "max_duration": 3600,
            "delay": 1.0,
            "concurrent_requests": 5,
            "respect_robots": True,
            "allow_external_links": False,
            "allow_subdomains": True,
        },
        "browser": {
            "headless": True,
            "timeout": 30,
            "viewport_width": 1920,
            "viewport_height": 1080,
            "user_agent": "Crawler/1.0",
        },
        "storage": {
            "database_url": "sqlite:///crawler.db",
            "session_timeout": 1800,
            "cache_size": 1000,
        },
        "logging": {
            "level": "WARNING",
            "file": "crawler.log",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "metrics": {
            "enabled": True,
            "collection_interval": 60,
            "retention_days": 30,
        },
        "llm": {
            "openai_api_key": "",
            "anthropic_api_key": "",
            "default_model": "openai/gpt-4",
        },
        "jobs": {
            "max_concurrent": 10,
            "retry_attempts": 1,
            "retry_delay": 5,
        },
    }