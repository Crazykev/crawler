"""Main entry point for the Crawler application."""

import sys
from typing import Optional

from .cli.main import cli
from .foundation.logging import setup_logging
from .foundation.config import ConfigManager


def main(args: Optional[list] = None) -> int:
    """Main entry point for the crawler application.
    
    Args:
        args: Command line arguments (defaults to sys.argv)
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Initialize configuration and logging
        config_manager = ConfigManager()
        setup_logging(config_manager.get_setting("log_level", "WARNING"))
        
        # Run CLI interface
        return cli(args=args, standalone_mode=False)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())