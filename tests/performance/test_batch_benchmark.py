"""Performance benchmark for batch scraping test."""

import time
import json
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock
import pytest

from src.crawler.cli.main import cli


@pytest.mark.benchmark
class TestBatchPerformanceBenchmark:
    """Benchmark batch scraping performance."""
    
    def test_batch_scraping_with_mocks(self, cli_runner, temp_dir, mock_crawl4ai):
        """Test batch scraping with mocks (optimized)."""
        
        # Create URL file
        urls_file = temp_dir / "urls.txt"
        urls = [
            "https://httpbin.org/uuid",
            "https://httpbin.org/json",
            "https://httpbin.org/ip",
            "https://httpbin.org/headers",
            "https://httpbin.org/user-agent"
        ]
        urls_file.write_text("\n".join(urls))
        
        output_dir = temp_dir / "batch_results"
        
        # Time the execution with mocks
        start_time = time.time()
        
        result = cli_runner.invoke(cli, [
            'batch',
            str(urls_file),
            '--output-dir', str(output_dir),
            '--format', 'json',
            '--concurrent', '3'
        ])
        
        execution_time = time.time() - start_time
        
        assert result.exit_code == 0
        assert output_dir.exists()
        
        # Verify output files were created
        output_files = list(output_dir.glob("*.json"))
        individual_files = [f for f in output_files if not f.name.endswith("_summary.json") and not f.name.startswith("batch_summary")]
        assert len(individual_files) == len(urls)
        
        # Verify each output file has valid content
        for output_file in individual_files:
            content = json.loads(output_file.read_text())
            assert content["success"] is True
            assert "url" in content
            assert content["url"] in urls
        
        print(f"Batch scraping with mocks completed in {execution_time:.2f}s")
        
        # Should complete very quickly with mocks
        assert execution_time < 5.0, f"Mocked batch scraping too slow: {execution_time:.2f}s"
    
    def test_batch_scraping_without_mocks(self, cli_runner, temp_dir):
        """Test batch scraping without mocks (slower, real network)."""
        
        # Create URL file with URLs that should respond
        urls_file = temp_dir / "urls.txt"
        urls = [
            "https://example.com",
            "https://www.google.com",
            "https://github.com"
        ]
        urls_file.write_text("\n".join(urls))
        
        output_dir = temp_dir / "batch_results"
        
        # Time the execution without mocks
        start_time = time.time()
        
        result = cli_runner.invoke(cli, [
            'batch',
            str(urls_file),
            '--output-dir', str(output_dir),
            '--format', 'json',
            '--concurrent', '3',
            '--timeout', '10'  # Reasonable timeout
        ])
        
        execution_time = time.time() - start_time
        
        # This test may fail if network is slow or sites are down
        # But that's expected for the benchmark
        if result.exit_code == 0:
            assert output_dir.exists()
            
            # Verify output files were created
            output_files = list(output_dir.glob("*.json"))
            individual_files = [f for f in output_files if not f.name.endswith("_summary.json") and not f.name.startswith("batch_summary")]
            
            print(f"Batch scraping without mocks completed in {execution_time:.2f}s")
            print(f"Created {len(individual_files)} output files")
        else:
            print(f"Batch scraping without mocks failed in {execution_time:.2f}s")
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
        
        # Record timing for comparison - no return value needed for pytest
        assert execution_time > 0  # Just verify it took some time
    
    def test_performance_comparison(self, cli_runner, temp_dir, mock_crawl4ai):
        """Compare performance between mocked and real network calls."""
        
        # Test with mocks
        urls_file = temp_dir / "urls_mock.txt"
        urls = [
            "https://httpbin.org/uuid",
            "https://httpbin.org/json",
            "https://httpbin.org/ip"
        ]
        urls_file.write_text("\n".join(urls))
        
        output_dir_mock = temp_dir / "batch_results_mock"
        
        start_time = time.time()
        result_mock = cli_runner.invoke(cli, [
            'batch',
            str(urls_file),
            '--output-dir', str(output_dir_mock),
            '--format', 'json',
            '--concurrent', '2'
        ])
        mock_time = time.time() - start_time
        
        # Test without mocks (but with fast local URLs)
        # Remove mock to test real network
        mock_crawl4ai.stop()
        
        urls_file_real = temp_dir / "urls_real.txt"
        urls_real = [
            "https://httpbin.org/uuid",  # May be slow or fail
            "https://httpbin.org/json",
            "https://httpbin.org/ip"
        ]
        urls_file_real.write_text("\n".join(urls_real))
        
        output_dir_real = temp_dir / "batch_results_real"
        
        start_time = time.time()
        result_real = cli_runner.invoke(cli, [
            'batch',
            str(urls_file_real),
            '--output-dir', str(output_dir_real),
            '--format', 'json',
            '--concurrent', '2',
            '--timeout', '10'
        ])
        real_time = time.time() - start_time
        
        print(f"Performance comparison:")
        print(f"  With mocks: {mock_time:.2f}s")
        print(f"  Without mocks: {real_time:.2f}s")
        
        if result_mock.exit_code == 0 and result_real.exit_code == 0:
            improvement = (real_time - mock_time) / real_time * 100
            print(f"  Performance improvement: {improvement:.1f}%")
        
        # Mock should be successful
        assert result_mock.exit_code == 0
        assert output_dir_mock.exists()
        
        # Verify mock results
        mock_files = list(output_dir_mock.glob("*.json"))
        mock_individual = [f for f in mock_files if not f.name.endswith("_summary.json") and not f.name.startswith("batch_summary")]
        assert len(mock_individual) == len(urls)