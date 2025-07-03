"""
Crawler - A comprehensive web scraping and crawling solution built on crawl4ai.

This package provides three interface methods:
1. CLI Interface - Command-line interface for direct usage
2. Firecrawl-compatible API - Drop-in replacement for Firecrawl
3. Native REST API - Optimized RESTful API (future)

The system leverages crawl4ai for all web crawling operations while providing
a unified architecture with SQLite storage for Phase 1 development.
"""

from .version import __version__

__all__ = ["__version__"]