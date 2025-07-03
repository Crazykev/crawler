"""Job management for asynchronous task execution."""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import get_database_manager
from ..database.models.jobs import JobQueue, JobStatus, JobType
from ..foundation.config import get_config_manager
from ..foundation.logging import get_logger
from ..foundation.errors import (
    handle_error, ResourceError, ValidationError, ErrorContext
)
from ..foundation.metrics import get_metrics_collector, timer


@dataclass
class Job:
    """Represents a job to be executed."""
    job_id: str
    job_type: JobType
    job_data: Dict[str, Any]
    priority: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "job_data": self.job_data,
            "priority": self.priority,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class JobResult:
    """Represents the result of a job execution."""
    job_id: str
    success: bool
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    completed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "job_id": self.job_id,
            "success": self.success,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
            "completed_at": self.completed_at.isoformat()
        }


class JobManager:
    """Manages asynchronous job execution and queuing."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config_manager = get_config_manager()
        self.metrics = get_metrics_collector()
        self.db_manager = get_database_manager()
        
        # Job execution
        self._workers: List[asyncio.Task] = []
        self._worker_count = 0
        self._max_workers = self.config_manager.get_setting("global.max_workers", 10)
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # Job handlers
        self._job_handlers: Dict[JobType, Callable] = {}
        
        # Metrics tracking
        self._active_jobs: Dict[str, datetime] = {}
    
    def register_handler(self, job_type: JobType, handler: Callable) -> None:
        """Register a handler for a specific job type.
        
        Args:
            job_type: Type of job
            handler: Async function to handle the job
        """
        self._job_handlers[job_type] = handler
        self.logger.info(f"Registered handler for job type: {job_type.value}")
    
    async def start(self, worker_count: Optional[int] = None) -> None:
        """Start the job manager and worker tasks.
        
        Args:
            worker_count: Number of worker tasks to start
        """
        if self._running:
            self.logger.warning("Job manager is already running")
            return
        
        if worker_count is None:
            worker_count = self._max_workers
        
        self._worker_count = worker_count
        self._running = True
        self._shutdown_event.clear()
        
        # Start worker tasks
        for i in range(worker_count):
            worker_task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker_task)
        
        self.logger.info(f"Job manager started with {worker_count} workers")
        self.metrics.set_gauge("job_manager.workers", worker_count)
    
    async def stop(self, timeout: float = 30.0) -> None:
        """Stop the job manager and all workers.
        
        Args:
            timeout: Maximum time to wait for workers to finish
        """
        if not self._running:
            return
        
        self.logger.info("Stopping job manager...")
        self._running = False
        self._shutdown_event.set()
        
        # Wait for workers to finish
        if self._workers:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                self.logger.warning("Some workers did not finish within timeout")
                # Cancel remaining workers
                for worker in self._workers:
                    if not worker.done():
                        worker.cancel()
        
        self._workers.clear()
        self.logger.info("Job manager stopped")
        self.metrics.set_gauge("job_manager.workers", 0)
    
    async def submit_job(
        self,
        job_type: JobType,
        job_data: Dict[str, Any],
        priority: int = 0,
        max_retries: int = 3,
        job_id: Optional[str] = None
    ) -> str:
        """Submit a job for execution.
        
        Args:
            job_type: Type of job
            job_data: Job data/parameters
            priority: Job priority (higher = more important)
            max_retries: Maximum retry attempts
            job_id: Optional custom job ID
            
        Returns:
            Job ID
        """
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        # Validate job data
        if not isinstance(job_data, dict):
            raise ValidationError("Job data must be a dictionary")
        
        if job_type not in self._job_handlers:
            raise ValidationError(f"No handler registered for job type: {job_type.value}")
        
        with timer("job_manager.submit_job"):
            try:
                async with self.db_manager.get_session() as session:
                    # Create job queue entry
                    job_entry = JobQueue(
                        job_id=job_id,
                        job_type=job_type,
                        status=JobStatus.PENDING,
                        priority=priority,
                        job_data=job_data,
                        max_retries=max_retries
                    )
                    
                    session.add(job_entry)
                    await session.commit()
                    
                    self.metrics.increment_counter("job_manager.jobs.submitted")
                    self.metrics.increment_counter(f"job_manager.jobs.{job_type.value}.submitted")
                    self._update_queue_metrics()
                    
                    self.logger.info(f"Submitted job {job_id} (type: {job_type.value}, priority: {priority})")
                    return job_id
                    
            except Exception as e:
                error_msg = f"Failed to submit job: {e}"
                self.logger.error(error_msg)
                handle_error(ResourceError(error_msg, resource_type="database"))
                raise
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status information or None if not found
        """
        with timer("job_manager.get_job_status"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = select(JobQueue).where(JobQueue.job_id == job_id)
                    result = await session.execute(stmt)
                    job = result.scalar_one_or_none()
                    
                    if not job:
                        return None
                    
                    status_info = {
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "status": job.status.value,
                        "priority": job.priority,
                        "created_at": job.created_at.isoformat(),
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                        "retry_count": job.retry_count,
                        "max_retries": job.max_retries,
                        "error_message": job.error_message
                    }
                    
                    # Add execution time if completed
                    if job.started_at and job.completed_at:
                        execution_time = (job.completed_at - job.started_at).total_seconds()
                        status_info["execution_time"] = execution_time
                    
                    return status_info
                    
            except Exception as e:
                self.logger.error(f"Failed to get job status for {job_id}: {e}")
                return None
    
    async def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the result of a completed job.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job result or None if not found/not completed
        """
        with timer("job_manager.get_job_result"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = select(JobQueue).where(
                        and_(
                            JobQueue.job_id == job_id,
                            JobQueue.status == JobStatus.COMPLETED
                        )
                    )
                    result = await session.execute(stmt)
                    job = result.scalar_one_or_none()
                    
                    if not job:
                        return None
                    
                    return {
                        "job_id": job.job_id,
                        "success": True,
                        "result_data": job.result_data,
                        "completed_at": job.completed_at.isoformat(),
                        "execution_time": (job.completed_at - job.started_at).total_seconds() if job.started_at else None
                    }
                    
            except Exception as e:
                self.logger.error(f"Failed to get job result for {job_id}: {e}")
                return None
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if cancelled successfully
        """
        with timer("job_manager.cancel_job"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = update(JobQueue).where(
                        and_(
                            JobQueue.job_id == job_id,
                            JobQueue.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
                        )
                    ).values(
                        status=JobStatus.CANCELLED,
                        completed_at=datetime.utcnow()
                    )
                    
                    result = await session.execute(stmt)
                    await session.commit()
                    
                    cancelled = result.rowcount > 0
                    if cancelled:
                        self.metrics.increment_counter("job_manager.jobs.cancelled")
                        self.logger.info(f"Cancelled job {job_id}")
                    
                    return cancelled
                    
            except Exception as e:
                self.logger.error(f"Failed to cancel job {job_id}: {e}")
                return False
    
    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List jobs with optional filtering.
        
        Args:
            status: Filter by job status
            job_type: Filter by job type
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            
        Returns:
            List of job information
        """
        with timer("job_manager.list_jobs"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = select(JobQueue)
                    
                    # Apply filters
                    if status:
                        stmt = stmt.where(JobQueue.status == status)
                    if job_type:
                        stmt = stmt.where(JobQueue.job_type == job_type)
                    
                    # Order by priority (desc) and created_at (asc)
                    stmt = stmt.order_by(
                        JobQueue.priority.desc(),
                        JobQueue.created_at.asc()
                    )
                    
                    # Apply pagination
                    stmt = stmt.offset(offset).limit(limit)
                    
                    result = await session.execute(stmt)
                    jobs = result.scalars().all()
                    
                    job_list = []
                    for job in jobs:
                        job_info = {
                            "job_id": job.job_id,
                            "job_type": job.job_type.value,
                            "status": job.status.value,
                            "priority": job.priority,
                            "created_at": job.created_at.isoformat(),
                            "started_at": job.started_at.isoformat() if job.started_at else None,
                            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                            "retry_count": job.retry_count,
                            "error_message": job.error_message
                        }
                        
                        # Add execution time if available
                        if job.started_at and job.completed_at:
                            execution_time = (job.completed_at - job.started_at).total_seconds()
                            job_info["execution_time"] = execution_time
                        
                        job_list.append(job_info)
                    
                    return job_list
                    
            except Exception as e:
                self.logger.error(f"Failed to list jobs: {e}")
                return []
    
    async def _worker_loop(self, worker_name: str) -> None:
        """Main worker loop for processing jobs.
        
        Args:
            worker_name: Name of the worker for logging
        """
        self.logger.info(f"Worker {worker_name} started")
        
        while self._running:
            try:
                # Get next job
                job = await self._get_next_job()
                if not job:
                    # No jobs available, wait a bit
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue
                    break
                
                # Process the job
                await self._process_job(job, worker_name)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1.0)  # Brief pause before continuing
        
        self.logger.info(f"Worker {worker_name} stopped")
    
    async def _get_next_job(self) -> Optional[JobQueue]:
        """Get the next job from the queue.
        
        Returns:
            Next job to process or None if no jobs available
        """
        try:
            async with self.db_manager.get_session() as session:
                # Get highest priority pending job
                stmt = select(JobQueue).where(
                    JobQueue.status == JobStatus.PENDING
                ).order_by(
                    JobQueue.priority.desc(),
                    JobQueue.created_at.asc()
                ).limit(1)
                
                result = await session.execute(stmt)
                job = result.scalar_one_or_none()
                
                if job:
                    # Mark as running
                    job.mark_started()
                    await session.commit()
                    
                    self._active_jobs[job.job_id] = datetime.utcnow()
                    self.metrics.increment_counter("job_manager.jobs.started")
                    self._update_queue_metrics()
                
                return job
                
        except Exception as e:
            self.logger.error(f"Failed to get next job: {e}")
            return None
    
    async def _process_job(self, job: JobQueue, worker_name: str) -> None:
        """Process a single job.
        
        Args:
            job: Job to process
            worker_name: Name of the worker
        """
        start_time = datetime.utcnow()
        
        try:
            # Get handler for job type
            handler = self._job_handlers.get(job.job_type)
            if not handler:
                raise ValueError(f"No handler registered for job type: {job.job_type.value}")
            
            self.logger.info(f"Worker {worker_name} processing job {job.job_id} (type: {job.job_type.value})")
            
            # Execute the job
            result = await handler(job.job_data)
            
            # Mark as completed
            async with self.db_manager.get_session() as session:
                stmt = select(JobQueue).where(JobQueue.job_id == job.job_id)
                db_result = await session.execute(stmt)
                db_job = db_result.scalar_one_or_none()
                
                if db_job:
                    db_job.mark_completed(result if isinstance(result, dict) else {"result": result})
                    await session.commit()
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.metrics.increment_counter("job_manager.jobs.completed")
            self.metrics.increment_counter(f"job_manager.jobs.{job.job_type.value}.completed")
            self.metrics.record_timing("job_manager.job_execution", execution_time)
            
            self.logger.info(f"Job {job.job_id} completed successfully in {execution_time:.2f}s")
            
        except Exception as e:
            error_msg = str(e)
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Mark as failed and check if should retry
            async with self.db_manager.get_session() as session:
                stmt = select(JobQueue).where(JobQueue.job_id == job.job_id)
                db_result = await session.execute(stmt)
                db_job = db_result.scalar_one_or_none()
                
                if db_job:
                    db_job.mark_failed(error_msg)
                    
                    # Check if can retry
                    if db_job.can_retry():
                        db_job.status = JobStatus.PENDING  # Reset to pending for retry
                        self.logger.warning(f"Job {job.job_id} failed, will retry ({db_job.retry_count}/{db_job.max_retries}): {error_msg}")
                        self.metrics.increment_counter("job_manager.jobs.retried")
                    else:
                        self.logger.error(f"Job {job.job_id} failed permanently after {db_job.retry_count} attempts: {error_msg}")
                        self.metrics.increment_counter("job_manager.jobs.failed")
                        self.metrics.increment_counter(f"job_manager.jobs.{job.job_type.value}.failed")
                    
                    await session.commit()
            
            # Handle the error
            context = ErrorContext(
                operation="process_job",
                job_id=job.job_id,
                metadata={"job_type": job.job_type.value, "worker": worker_name}
            )
            handle_error(e, context)
            
        finally:
            # Remove from active jobs tracking
            self._active_jobs.pop(job.job_id, None)
            self._update_queue_metrics()
    
    def _update_queue_metrics(self) -> None:
        """Update job queue metrics."""
        asyncio.create_task(self._async_update_queue_metrics())
    
    async def _async_update_queue_metrics(self) -> None:
        """Async helper to update queue metrics."""
        try:
            async with self.db_manager.get_session() as session:
                # Count jobs by status
                for status in JobStatus:
                    stmt = select(JobQueue).where(JobQueue.status == status)
                    result = await session.execute(stmt)
                    count = len(result.scalars().all())
                    self.metrics.set_gauge(f"job_manager.jobs.{status.value}", count)
                
                # Active jobs
                self.metrics.set_gauge("job_manager.jobs.active", len(self._active_jobs))
                
        except Exception as e:
            self.logger.error(f"Failed to update queue metrics: {e}")
    
    async def cleanup_completed_jobs(self, older_than: Optional[timedelta] = None) -> int:
        """Clean up old completed jobs.
        
        Args:
            older_than: Clean jobs older than this timedelta
            
        Returns:
            Number of jobs cleaned up
        """
        if older_than is None:
            older_than = timedelta(days=7)  # Default: 7 days
        
        cutoff_time = datetime.utcnow() - older_than
        
        with timer("job_manager.cleanup_completed_jobs"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = delete(JobQueue).where(
                        and_(
                            JobQueue.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]),
                            JobQueue.completed_at < cutoff_time
                        )
                    )
                    
                    result = await session.execute(stmt)
                    await session.commit()
                    
                    cleaned_count = result.rowcount
                    if cleaned_count > 0:
                        self.logger.info(f"Cleaned up {cleaned_count} old completed jobs")
                        self.metrics.record_metric("job_manager.jobs.cleaned", cleaned_count)
                    
                    return cleaned_count
                    
            except Exception as e:
                self.logger.error(f"Failed to cleanup completed jobs: {e}")
                return 0
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get job manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            async with self.db_manager.get_session() as session:
                stats = {
                    "workers": {
                        "count": self._worker_count,
                        "running": self._running,
                        "active_jobs": len(self._active_jobs)
                    },
                    "jobs": {}
                }
                
                # Count jobs by status
                for status in JobStatus:
                    stmt = select(JobQueue).where(JobQueue.status == status)
                    result = await session.execute(stmt)
                    count = len(result.scalars().all())
                    stats["jobs"][status.value] = count
                
                # Count jobs by type
                stats["jobs_by_type"] = {}
                for job_type in JobType:
                    stmt = select(JobQueue).where(JobQueue.job_type == job_type)
                    result = await session.execute(stmt)
                    count = len(result.scalars().all())
                    stats["jobs_by_type"][job_type.value] = count
                
                # Registered handlers
                stats["handlers"] = list(self._job_handlers.keys())
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}


# Global job manager instance
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get the global job manager instance."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager