"""Metrics collection and monitoring for the Crawler system."""

import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional, Union, Deque

from .logging import get_logger


@dataclass
class MetricValue:
    """Individual metric value with timestamp."""
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    name: str
    count: int
    sum: float
    min: float
    max: float
    avg: float
    latest: float
    latest_timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_values(cls, name: str, values: List[MetricValue]) -> "MetricSummary":
        """Create summary from list of metric values."""
        if not values:
            return cls(
                name=name,
                count=0,
                sum=0.0,
                min=0.0,
                max=0.0,
                avg=0.0,
                latest=0.0,
                latest_timestamp=datetime.utcnow()
            )
        
        numeric_values = [v.value for v in values]
        latest_value = values[-1]
        
        return cls(
            name=name,
            count=len(values),
            sum=sum(numeric_values),
            min=min(numeric_values),
            max=max(numeric_values),
            avg=sum(numeric_values) / len(numeric_values),
            latest=latest_value.value,
            latest_timestamp=latest_value.timestamp,
            tags=latest_value.tags.copy()
        )


class MetricsCollector:
    """Collects and aggregates system metrics."""
    
    def __init__(self, max_values_per_metric: int = 1000):
        self.logger = get_logger(__name__)
        self.max_values_per_metric = max_values_per_metric
        
        # Storage for metrics
        self._metrics: Dict[str, Deque[MetricValue]] = defaultdict(
            lambda: deque(maxlen=self.max_values_per_metric)
        )
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        
        # Thread safety
        self._lock = Lock()
        
        # System start time for uptime calculation
        self._start_time = datetime.utcnow()
    
    def record_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags for the metric
            timestamp: Optional timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        if tags is None:
            tags = {}
        
        metric_value = MetricValue(value=value, timestamp=timestamp, tags=tags)
        
        with self._lock:
            self._metrics[name].append(metric_value)
    
    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric.
        
        Args:
            name: Counter name
            value: Value to add (default: 1.0)
            tags: Optional tags
        """
        with self._lock:
            self._counters[name] += value
        
        # Also record as a regular metric for historical tracking
        self.record_metric(name, self._counters[name], tags)
    
    def set_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric value.
        
        Args:
            name: Gauge name
            value: Current value
            tags: Optional tags
        """
        with self._lock:
            self._gauges[name] = value
        
        # Also record as a regular metric for historical tracking
        self.record_metric(name, value, tags)
    
    def record_timing(
        self,
        name: str,
        duration: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a timing metric.
        
        Args:
            name: Timer name
            duration: Duration in seconds
            tags: Optional tags
        """
        self.record_metric(f"{name}.duration", duration, tags)
        self.increment_counter(f"{name}.count", tags=tags)
    
    @contextmanager
    def timer(self, name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager for timing operations.
        
        Args:
            name: Timer name
            tags: Optional tags
            
        Usage:
            with metrics.timer("operation_name"):
                # perform operation
                pass
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_timing(name, duration, tags)
    
    def get_metric_summary(self, name: str) -> Optional[MetricSummary]:
        """Get summary statistics for a metric.
        
        Args:
            name: Metric name
            
        Returns:
            MetricSummary or None if metric doesn't exist
        """
        with self._lock:
            if name not in self._metrics:
                return None
            
            values = list(self._metrics[name])
        
        return MetricSummary.from_values(name, values)
    
    def get_all_metrics_summary(self) -> Dict[str, MetricSummary]:
        """Get summary statistics for all metrics.
        
        Returns:
            Dictionary of metric summaries
        """
        summaries = {}
        
        with self._lock:
            metric_names = list(self._metrics.keys())
        
        for name in metric_names:
            summary = self.get_metric_summary(name)
            if summary:
                summaries[name] = summary
        
        return summaries
    
    def get_counter_value(self, name: str) -> float:
        """Get current counter value.
        
        Args:
            name: Counter name
            
        Returns:
            Current counter value
        """
        with self._lock:
            return self._counters.get(name, 0.0)
    
    def get_gauge_value(self, name: str) -> float:
        """Get current gauge value.
        
        Args:
            name: Gauge name
            
        Returns:
            Current gauge value
        """
        with self._lock:
            return self._gauges.get(name, 0.0)
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-level metrics.
        
        Returns:
            Dictionary of system metrics
        """
        import psutil
        import os
        
        current_time = datetime.utcnow()
        uptime = current_time - self._start_time
        
        try:
            process = psutil.Process(os.getpid())
            
            system_metrics = {
                "uptime_seconds": uptime.total_seconds(),
                "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_percent": process.cpu_percent(),
                "open_files": len(process.open_files()) if hasattr(process, 'open_files') else 0,
                "threads": process.num_threads(),
                "timestamp": current_time.isoformat()
            }
            
            # System-wide metrics
            system_metrics.update({
                "system_memory_percent": psutil.virtual_memory().percent,
                "system_cpu_percent": psutil.cpu_percent(),
                "system_disk_percent": psutil.disk_usage('/').percent
            })
            
        except Exception as e:
            self.logger.warning(f"Failed to collect system metrics: {e}")
            system_metrics = {
                "uptime_seconds": uptime.total_seconds(),
                "timestamp": current_time.isoformat(),
                "error": str(e)
            }
        
        return system_metrics
    
    def get_business_metrics(self) -> Dict[str, Any]:
        """Get business-level metrics specific to crawling operations.
        
        Returns:
            Dictionary of business metrics
        """
        business_metrics = {
            # Scraping metrics
            "total_scrapes": self.get_counter_value("scrape.count"),
            "successful_scrapes": self.get_counter_value("scrape.success"),
            "failed_scrapes": self.get_counter_value("scrape.failure"),
            
            # Crawling metrics
            "total_crawls": self.get_counter_value("crawl.count"),
            "successful_crawls": self.get_counter_value("crawl.success"),
            "failed_crawls": self.get_counter_value("crawl.failure"),
            
            # Session metrics
            "active_sessions": self.get_gauge_value("sessions.active"),
            "total_sessions_created": self.get_counter_value("sessions.created"),
            "total_sessions_closed": self.get_counter_value("sessions.closed"),
            
            # Job metrics
            "jobs_pending": self.get_gauge_value("jobs.pending"),
            "jobs_running": self.get_gauge_value("jobs.running"),
            "jobs_completed": self.get_counter_value("jobs.completed"),
            "jobs_failed": self.get_counter_value("jobs.failed"),
            
            # Cache metrics
            "cache_hits": self.get_counter_value("cache.hits"),
            "cache_misses": self.get_counter_value("cache.misses"),
            "cache_size": self.get_gauge_value("cache.size"),
        }
        
        # Calculate derived metrics
        total_scrapes = business_metrics["total_scrapes"]
        if total_scrapes > 0:
            business_metrics["scrape_success_rate"] = (
                business_metrics["successful_scrapes"] / total_scrapes
            )
        
        total_crawls = business_metrics["total_crawls"]
        if total_crawls > 0:
            business_metrics["crawl_success_rate"] = (
                business_metrics["successful_crawls"] / total_crawls
            )
        
        cache_requests = business_metrics["cache_hits"] + business_metrics["cache_misses"]
        if cache_requests > 0:
            business_metrics["cache_hit_rate"] = (
                business_metrics["cache_hits"] / cache_requests
            )
        
        return business_metrics
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance-related metrics.
        
        Returns:
            Dictionary of performance metrics
        """
        performance_metrics = {}
        
        # Get timing summaries for key operations
        timing_metrics = [
            "scrape.duration",
            "crawl.duration",
            "extraction.duration",
            "database.query.duration",
            "http.request.duration"
        ]
        
        for metric_name in timing_metrics:
            summary = self.get_metric_summary(metric_name)
            if summary and summary.count > 0:
                performance_metrics[metric_name] = {
                    "avg_ms": summary.avg * 1000,
                    "min_ms": summary.min * 1000,
                    "max_ms": summary.max * 1000,
                    "count": summary.count,
                    "latest_ms": summary.latest * 1000
                }
        
        return performance_metrics
    
    def export_metrics(
        self,
        format: str = "dict",
        include_system: bool = True,
        include_business: bool = True,
        include_performance: bool = True
    ) -> Union[Dict[str, Any], str]:
        """Export all metrics in specified format.
        
        Args:
            format: Export format ('dict', 'json', 'prometheus')
            include_system: Include system metrics
            include_business: Include business metrics
            include_performance: Include performance metrics
            
        Returns:
            Metrics in specified format
        """
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "collector_info": {
                "max_values_per_metric": self.max_values_per_metric,
                "total_metrics": len(self._metrics)
            }
        }
        
        if include_system:
            metrics["system"] = self.get_system_metrics()
        
        if include_business:
            metrics["business"] = self.get_business_metrics()
        
        if include_performance:
            metrics["performance"] = self.get_performance_metrics()
        
        if format == "dict":
            return metrics
        elif format == "json":
            import json
            return json.dumps(metrics, indent=2, default=str)
        elif format == "prometheus":
            return self._export_prometheus_format(metrics)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _export_prometheus_format(self, metrics: Dict[str, Any]) -> str:
        """Export metrics in Prometheus format.
        
        Args:
            metrics: Metrics dictionary
            
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        
        def add_metric(name: str, value: Union[int, float], help_text: str = ""):
            if help_text:
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        
        # System metrics
        if "system" in metrics:
            sys_metrics = metrics["system"]
            add_metric("crawler_uptime_seconds", sys_metrics.get("uptime_seconds", 0))
            add_metric("crawler_memory_usage_bytes", sys_metrics.get("memory_usage_mb", 0) * 1024 * 1024)
            add_metric("crawler_cpu_percent", sys_metrics.get("cpu_percent", 0))
            add_metric("crawler_threads_total", sys_metrics.get("threads", 0))
        
        # Business metrics
        if "business" in metrics:
            biz_metrics = metrics["business"]
            add_metric("crawler_scrapes_total", biz_metrics.get("total_scrapes", 0))
            add_metric("crawler_crawls_total", biz_metrics.get("total_crawls", 0))
            add_metric("crawler_sessions_active", biz_metrics.get("active_sessions", 0))
            add_metric("crawler_jobs_pending", biz_metrics.get("jobs_pending", 0))
            add_metric("crawler_cache_hits_total", biz_metrics.get("cache_hits", 0))
        
        return "\n".join(lines)
    
    def clear_metrics(self, older_than: Optional[timedelta] = None) -> int:
        """Clear old metrics to free memory.
        
        Args:
            older_than: Clear metrics older than this timedelta (default: 1 hour)
            
        Returns:
            Number of metric values cleared
        """
        if older_than is None:
            older_than = timedelta(hours=1)
        
        cutoff_time = datetime.utcnow() - older_than
        cleared_count = 0
        
        with self._lock:
            for metric_name, values in self._metrics.items():
                original_length = len(values)
                
                # Filter out old values
                while values and values[0].timestamp < cutoff_time:
                    values.popleft()
                    cleared_count += 1
        
        if cleared_count > 0:
            self.logger.info(f"Cleared {cleared_count} old metric values")
        
        return cleared_count


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# Convenience functions for common metric operations
def record_metric(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Record a metric value."""
    get_metrics_collector().record_metric(name, value, tags)


def increment_counter(name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
    """Increment a counter."""
    get_metrics_collector().increment_counter(name, value, tags)


def set_gauge(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Set a gauge value."""
    get_metrics_collector().set_gauge(name, value, tags)


def record_timing(name: str, duration: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Record a timing metric."""
    get_metrics_collector().record_timing(name, duration, tags)


def timer(name: str, tags: Optional[Dict[str, str]] = None):
    """Context manager for timing operations."""
    return get_metrics_collector().timer(name, tags)