"""Tests for crawl service link discovery and deduplication."""

import pytest

from src.crawler.services.crawl import CrawlService, CrawlRule


@pytest.mark.asyncio
async def test_discover_links_strips_fragments_and_dedupes():
    crawl_service = CrawlService()
    rules = CrawlRule(max_depth=2, allow_external_links=False, allow_subdomains=True)

    page_url = "https://www.home-assistant.io/docs/blueprint/selectors/"
    result = {
        "success": True,
        "metadata": {
            "links": [
                {"url": "#example-floor-selectors"},
                {"url": "/docs/blueprint/selectors/#example-floor-selectors"},
                {"url": "https://www.home-assistant.io/docs/blueprint/selectors/#example-floor-selectors"},
                {"url": "https://www.home-assistant.io/docs/blueprint/selectors/"},
            ]
        },
    }

    discovered = await crawl_service._discover_links(page_url, result, rules)

    # All fragment variations should normalize to the same page URL and be returned once.
    assert discovered == ["https://www.home-assistant.io/docs/blueprint/selectors/"]

