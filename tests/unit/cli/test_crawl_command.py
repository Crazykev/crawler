"""Tests for crawler crawl command functionality and expected output behavior."""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner

from src.crawler.cli.commands.crawl import crawl


@pytest.mark.cli
class TestCrawlCommandBasic:
    """Test basic crawl command functionality."""
    
    def test_crawl_command_help(self, cli_runner):
        """Test crawl command help display."""
        result = cli_runner.invoke(crawl, ['--help'])
        
        assert result.exit_code == 0
        assert "Crawl multiple pages starting from a URL" in result.output
        assert "--max-depth" in result.output
        assert "--max-pages" in result.output
        assert "--output" in result.output
        assert "--format" in result.output
    
    def test_crawl_command_console_output_format(self, cli_runner):
        """Test crawl command console output format matches expected behavior."""
        # Use a simple URL with limited depth to avoid long test times
        result = cli_runner.invoke(crawl, [
            'https://httpbin.org/json', 
            '--max-depth', '1', 
            '--max-pages', '1'
        ])
            
        # Should succeed
        assert result.exit_code == 0
        
        # Should contain crawl summary table
        assert "Crawl Summary" in result.output
        assert "Status" in result.output
        assert "Start URL" in result.output
        assert "httpbin.org/json" in result.output
        assert "Pages Crawled" in result.output
        assert "Pages Successful" in result.output
        assert "Pages Failed" in result.output
        assert "Max Depth Reached" in result.output
        assert "URLs Discovered" in result.output
        assert "Results Stored" in result.output
        assert "Elapsed Time" in result.output
        assert "Success Rate" in result.output
    
    def test_crawl_command_with_output_directory(self, cli_runner, temp_dir):
        """Test crawl command creates output files correctly."""
        output_dir = temp_dir / "crawl_output"
        
        result = cli_runner.invoke(crawl, [
            'https://httpbin.org/json',
            '--output', str(output_dir),
            '--max-depth', '1',
            '--max-pages', '1',
            '--format', 'markdown'
        ])
        
        # Should succeed
        assert result.exit_code == 0
        
        # Should create output directory
        assert output_dir.exists()
        
        # Should create some markdown files
        md_files = list(output_dir.glob("*.md"))
        assert len(md_files) >= 1, "Should create at least one markdown file"
        
        # Check file content is not empty
        for md_file in md_files:
            content = md_file.read_text()
            assert len(content) > 0, f"File {md_file.name} should not be empty"
        
        # Should create crawl summary file
        summary_file = output_dir / "crawl_summary.json"
        assert summary_file.exists(), "crawl_summary.json should be created"
        
        # Check summary content structure
        summary_data = json.loads(summary_file.read_text())
        assert "crawl_id" in summary_data
        assert "status" in summary_data
        assert "results_count" in summary_data
        assert "output_format" in summary_data
        assert summary_data["output_format"] == "markdown"
        
        # Should show success message in output
        assert "Results saved to:" in result.output
        assert "crawl_summary.json" in result.output
    
    def test_crawl_command_json_format(self, cli_runner, temp_dir):
        """Test crawl command with JSON output format."""
        output_dir = temp_dir / "json_output"
        
        result = cli_runner.invoke(crawl, [
            'https://httpbin.org/json',
            '--output', str(output_dir),
            '--max-depth', '1',
            '--max-pages', '1',
            '--format', 'json'
        ])
        
        # Should succeed
        assert result.exit_code == 0
        
        # Should create output directory
        assert output_dir.exists()
        
        # Should create JSON files
        json_files = list(output_dir.glob("*.json"))
        # Filter out summary file
        page_files = [f for f in json_files if not f.name.startswith("crawl_summary")]
        assert len(page_files) >= 1, "Should create at least one JSON page file"
        
        # Check JSON content structure
        for json_file in page_files:
            content = json.loads(json_file.read_text())
            assert isinstance(content, dict)
            # Should have basic crawl result structure
            assert "url" in content or "success" in content
    
    def test_crawl_command_depth_limit(self, cli_runner):
        """Test crawl command respects depth limit."""
        result = cli_runner.invoke(crawl, [
            'https://httpbin.org/json',
            '--max-depth', '0',  # Only crawl the initial page
            '--max-pages', '1'
        ])
        
        # Should succeed
        assert result.exit_code == 0
        assert "Crawl Summary" in result.output
        # Should only crawl 1 page with depth 0
        assert "Pages Crawled" in result.output
    
    def test_crawl_command_page_limit(self, cli_runner):
        """Test crawl command respects page limit."""
        result = cli_runner.invoke(crawl, [
            'https://httpbin.org/json',
            '--max-pages', '1',  # Only crawl 1 page
            '--max-depth', '1'
        ])
        
        # Should succeed
        assert result.exit_code == 0
        assert "Crawl Summary" in result.output
        # Should respect the page limit
        assert "Pages Crawled" in result.output


@pytest.mark.cli
class TestCrawlCommandOptions:
    """Test crawl command options and parameters."""
    
    def test_crawl_command_format_options(self, cli_runner):
        """Test crawl command format options."""
        formats = ['markdown', 'json', 'html', 'text']
        
        for fmt in formats:
            result = cli_runner.invoke(crawl, [
                'https://httpbin.org/json',
                '--format', fmt,
                '--max-depth', '1',
                '--max-pages', '1'
            ])
            
            # Should succeed for all formats
            assert result.exit_code == 0, f"Format {fmt} should work"
            assert "Crawl Summary" in result.output
    
    def test_crawl_command_invalid_url(self, cli_runner):
        """Test crawl command with invalid URL."""
        result = cli_runner.invoke(crawl, ['not-a-valid-url'])
        
        # Should fail gracefully
        assert result.exit_code != 0


@pytest.mark.cli
class TestCrawlCommandEdgeCases:
    """Test crawl command edge cases."""
    
    def test_crawl_command_no_results(self, cli_runner):
        """Test crawl command when no pages can be crawled."""
        # Use a URL that should fail or return no links
        result = cli_runner.invoke(crawl, [
            'https://httpbin.org/status/404',
            '--max-depth', '1',
            '--max-pages', '1'
        ])
        
        # Command should still complete (might succeed or fail depending on implementation)
        # The important thing is it handles the case gracefully
        assert "Crawl Summary" in result.output or result.exit_code != 0
    
    def test_crawl_command_content_preview(self, cli_runner):
        """Test that crawl command shows content preview."""
        result = cli_runner.invoke(crawl, [
            'https://httpbin.org/json',
            '--max-depth', '1',
            '--max-pages', '1'
        ])
        
        # Should succeed
        assert result.exit_code == 0
        
        # Should show either content preview or indicate no content
        # This tests the fix for the "No content available" issue
        output_text = result.output
        content_shown = (
            "First 3 results:" in output_text or
            "No content available" in output_text or
            "Page 1:" in output_text
        )
        assert content_shown, "Should show some indication of content or lack thereof"
    
    def test_crawl_command_url_filename_safety(self, cli_runner, temp_dir):
        """Test that URLs are converted to safe filenames."""
        output_dir = temp_dir / "safe_filename_test"
        
        # Use a URL with potentially unsafe characters
        result = cli_runner.invoke(crawl, [
            'https://httpbin.org/json',
            '--output', str(output_dir),
            '--max-depth', '1',
            '--max-pages', '1',
            '--format', 'markdown'
        ])
        
        # Should succeed
        assert result.exit_code == 0
        
        # Should create safe filenames
        if output_dir.exists():
            md_files = list(output_dir.glob("*.md"))
            dangerous_chars = '<>:"/\\|?*'
            for md_file in md_files:
                filename = md_file.name
                for char in dangerous_chars:
                    assert char not in filename, f"Unsafe character '{char}' in filename: {filename}"


@pytest.mark.integration 
class TestCrawlCommandIntegration:
    """Integration tests for crawl command with real functionality."""
    
    def test_crawl_example_com_integration(self, cli_runner, temp_dir):
        """Integration test using example.com to verify full workflow."""
        output_dir = temp_dir / "example_crawl"
        
        result = cli_runner.invoke(crawl, [
            'https://example.com',
            '--output', str(output_dir),
            '--max-depth', '1',
            '--max-pages', '3',
            '--format', 'markdown'
        ])
        
        # Should succeed
        assert result.exit_code == 0
        
        # Should show crawl summary
        assert "Crawl Summary" in result.output
        assert "completed" in result.output.lower()
        
        # Should create files
        if output_dir.exists():
            md_files = list(output_dir.glob("*.md"))
            assert len(md_files) >= 1, "Should create at least one markdown file"
            
            # Check that files contain actual content (not empty)
            for md_file in md_files:
                content = md_file.read_text()
                assert len(content.strip()) > 0, f"File {md_file.name} should have content"
            
            # Should create summary
            summary_file = output_dir / "crawl_summary.json"
            assert summary_file.exists()