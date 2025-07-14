"""Tests for CLI command implementations - Phase 1 TDD Requirements."""

import pytest
import asyncio
from click.testing import CliRunner
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from src.crawler.cli.commands.scrape import scrape
from src.crawler.cli.commands.config import config
from src.crawler.cli.commands.status import status
from src.crawler.foundation.errors import ValidationError, NetworkError


@pytest.mark.cli
class TestScrapeCommandImplementation:
    """Test actual scrape command implementation for Phase 1."""
    
    def test_scrape_command_basic_url(self, cli_runner, mock_crawl4ai):
        """Test scrape command with basic URL - Phase 1 requirement."""
        # GREEN: This should now pass with mocked crawl engine
        result = cli_runner.invoke(scrape, ['https://example.com'])
        
        # Phase 1 requirement: Basic scraping should work
        assert result.exit_code == 0
        assert "success" in result.output.lower() or "content" in result.output.lower() or "example" in result.output.lower()
    
    def test_scrape_command_with_output_file(self, cli_runner, temp_dir, mock_crawl4ai):
        """Test scrape command with output file - Phase 1 requirement."""
        output_file = temp_dir / "output.md"
        
        # GREEN: This should now pass with mocked crawl engine
        result = cli_runner.invoke(scrape, [
            'https://example.com',
            '--output', str(output_file),
            '--format', 'markdown'
        ])
        
        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.read_text().strip() != ""
    
    def test_scrape_command_with_css_extraction(self, cli_runner, mock_crawl4ai):
        """Test scrape command with CSS extraction strategy - Phase 1 requirement."""
        # GREEN: This should now pass with mocked crawl engine
        result = cli_runner.invoke(scrape, [
            'https://example.com',
            '--extract-strategy', 'css',
            '--css-selector', '.content'
        ])
        
        assert result.exit_code == 0
        assert "extracted" in result.output.lower() or "content" in result.output.lower() or "example" in result.output.lower()
    
    def test_scrape_command_invalid_url(self, cli_runner):
        """Test scrape command with invalid URL - Phase 1 requirement."""
        # RED: This should fail until proper validation is implemented
        result = cli_runner.invoke(scrape, ['not-a-url'])
        
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "error" in result.output.lower()
    
    def test_scrape_command_timeout_handling(self, cli_runner, mock_crawl4ai):
        """Test scrape command timeout handling - Phase 1 requirement."""
        # GREEN: Mock will handle timeout scenarios
        result = cli_runner.invoke(scrape, [
            'https://httpbin.org/delay/10',  # Slow endpoint
            '--timeout', '2'
        ])
        
        # Should either succeed quickly or fail with timeout message
        assert result.exit_code in [0, 1]
        if result.exit_code == 1:
            assert "timeout" in result.output.lower() or "failed" in result.output.lower()


@pytest.mark.cli
class TestConfigCommandImplementation:
    """Test config command implementation for Phase 1."""
    
    def test_config_show_command(self, cli_runner):
        """Test config show command - Phase 1 requirement."""
        # RED: This should fail until config show is implemented
        result = cli_runner.invoke(config, ['show'], obj={})
        
        assert result.exit_code == 0
        assert "scrape" in result.output or "crawl" in result.output
    
    def test_config_set_command(self, cli_runner):
        """Test config set command - Phase 1 requirement."""
        # RED: This should fail until config set is implemented
        result = cli_runner.invoke(config, ['set', 'scrape.timeout', '60'], obj={})
        
        assert result.exit_code == 0
        assert "set" in result.output.lower() or "updated" in result.output.lower()
    
    def test_config_get_command(self, cli_runner):
        """Test config get command - Phase 1 requirement."""
        # RED: This should fail until config get is implemented
        result = cli_runner.invoke(config, ['get', 'scrape.timeout'], obj={})
        
        assert result.exit_code == 0
        assert result.output.strip() != ""


@pytest.mark.cli
class TestStatusCommandImplementation:
    """Test status command implementation for Phase 1."""
    
    def test_status_command_basic(self, cli_runner):
        """Test basic status command - Phase 1 requirement."""
        # RED: This should fail until status command is implemented
        result = cli_runner.invoke(status, obj={})
        
        assert result.exit_code == 0
        assert any(keyword in result.output.lower() for keyword in [
            "status", "running", "ready", "database", "engine"
        ])
    
    def test_status_command_health_check(self, cli_runner):
        """Test status command health check - Phase 1 requirement."""
        # RED: This should fail until health checks are implemented
        result = cli_runner.invoke(status, ['--health'], obj={})
        
        assert result.exit_code == 0
        assert any(keyword in result.output.lower() for keyword in [
            "healthy", "ok", "ready", "pass", "fail"
        ])


@pytest.mark.integration
class TestCLIIntegrationPhase1:
    """Integration tests for Phase 1 CLI functionality."""
    
    def test_cli_scrape_to_file_workflow(self, cli_runner, temp_dir, mock_crawl4ai):
        """Test complete scrape-to-file workflow - Phase 1 integration."""
        output_file = temp_dir / "test_output.json"
        
        # GREEN: This should now pass with mocked crawl engine
        result = cli_runner.invoke(scrape, [
            'https://httpbin.org/json',  # Known JSON endpoint
            '--format', 'json',
            '--output', str(output_file)
        ])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        # Verify file content is valid JSON
        import json
        content = json.loads(output_file.read_text())
        assert isinstance(content, dict)
        assert "success" in content or "content" in content
    
    def test_cli_config_persistence(self, cli_runner, temp_dir):
        """Test config changes persist - Phase 1 integration."""
        config_file = temp_dir / "test_config.yaml"
        
        # RED: This should fail until config persistence is implemented
        # Set a config value
        result1 = cli_runner.invoke(config, [
            '--config', str(config_file),
            'set', 'scrape.timeout', '45'
        ], obj={})
        assert result1.exit_code == 0
        
        # Verify the value persists
        result2 = cli_runner.invoke(config, [
            '--config', str(config_file),
            'get', 'scrape.timeout'
        ], obj={})
        assert result2.exit_code == 0
        assert "45" in result2.output
    
    def test_cli_error_handling_integration(self, cli_runner, mock_crawl4ai):
        """Test CLI error handling integration - Phase 1 requirement."""
        # GREEN: Mock will automatically return failure result for invalid domains
        result = cli_runner.invoke(scrape, ['https://nonexistent-domain-12345.invalid'])
        
        assert result.exit_code != 0
        assert any(keyword in result.output.lower() for keyword in [
            "error", "failed", "connection", "network", "dns"
        ])


# These tests represent the TDD RED phase for Phase 1 completion
# They should FAIL initially and guide implementation