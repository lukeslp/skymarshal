#!/usr/bin/env python3
"""
Background task system for CAR file downloads and parallel processing.

Provides asynchronous task management for:
1. Background CAR file downloads with progress tracking
2. Parallel hydration processing for multiple users/DIDs
3. Task queuing and status monitoring
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union
from queue import Queue, Empty
import logging

from utils import safe_getattr, format_file_safe_name
from batch_processor import create_standard_batch_processor, BatchResult

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """Status of background tasks."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(Enum):
    """Types of background tasks."""
    CAR_DOWNLOAD = "car_download"
    HYDRATION = "hydration"
    PARALLEL_HYDRATION = "parallel_hydration"
    BACKUP_EXPORT = "backup_export"

@dataclass
class TaskProgress:
    """Progress tracking for background tasks."""
    current: int = 0
    total: int = 0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100

@dataclass
class BackgroundTask:
    """Represents a background task with progress tracking."""
    task_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: TaskProgress = field(default_factory=TaskProgress)
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()

class BackgroundTaskManager:
    """Manages background tasks with progress tracking and parallel execution."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, BackgroundTask] = {}
        self.active_futures: Dict[str, Any] = {}
        self._shutdown = False
        
    def create_task(
        self, 
        task_type: TaskType, 
        task_func: Callable,
        *args,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Create and queue a new background task.
        
        Args:
            task_type: Type of task to create
            task_func: Function to execute
            *args: Arguments for task function
            metadata: Optional task metadata
            **kwargs: Keyword arguments for task function
            
        Returns:
            Task ID for tracking
        """
        task_id = str(uuid.uuid4())
        task = BackgroundTask(
            task_id=task_id,
            task_type=task_type,
            metadata=metadata or {}
        )
        
        self.tasks[task_id] = task
        
        # Submit task to executor
        future = self.executor.submit(self._execute_task, task, task_func, *args, **kwargs)
        self.active_futures[task_id] = future
        
        logger.info(f"Created background task {task_id} of type {task_type.value}")
        return task_id
    
    def _execute_task(self, task: BackgroundTask, task_func: Callable, *args, **kwargs) -> Any:
        """Execute a background task with error handling and progress tracking."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        try:
            logger.info(f"Starting task {task.task_id}")
            
            # Add progress callback to kwargs if task function supports it
            if 'progress_callback' in kwargs or hasattr(task_func, '__code__') and 'progress_callback' in task_func.__code__.co_varnames:
                kwargs['progress_callback'] = lambda current, total, message="": self._update_progress(
                    task.task_id, current, total, message
                )
            
            result = task_func(*args, **kwargs)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            logger.info(f"Task {task.task_id} completed successfully in {task.duration:.2f}s")
            return result
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            
            logger.error(f"Task {task.task_id} failed: {e}")
            raise
        finally:
            # Clean up future reference
            self.active_futures.pop(task.task_id, None)
    
    def _update_progress(self, task_id: str, current: int, total: int, message: str = ""):
        """Update task progress."""
        task = self.tasks.get(task_id)
        if task:
            task.progress.current = current
            task.progress.total = total
            task.progress.message = message
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def get_tasks_by_type(self, task_type: TaskType) -> List[BackgroundTask]:
        """Get all tasks of a specific type."""
        return [task for task in self.tasks.values() if task.task_type == task_type]
    
    def get_active_tasks(self) -> List[BackgroundTask]:
        """Get all currently running tasks."""
        return [task for task in self.tasks.values() if task.status == TaskStatus.RUNNING]
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task if it's still pending or running."""
        task = self.tasks.get(task_id)
        future = self.active_futures.get(task_id)
        
        if task and future and not future.done():
            if future.cancel():
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                return True
        
        return False
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        
        to_remove = []
        for task_id, task in self.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] 
                and task.completed_at 
                and task.completed_at.timestamp() < cutoff):
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.tasks[task_id]
            logger.debug(f"Cleaned up old task {task_id}")
    
    def shutdown(self, wait: bool = True):
        """Shutdown task manager and executor."""
        self._shutdown = True
        self.executor.shutdown(wait=wait)

class CARDownloadManager:
    """Specialized manager for CAR file downloads with backup support."""
    
    def __init__(self, task_manager: BackgroundTaskManager):
        self.task_manager = task_manager
        self.download_cache: Dict[str, str] = {}  # handle -> task_id mapping
    
    def start_car_download(
        self, 
        auth_manager, 
        handle: str, 
        data_manager,
        background: bool = True
    ) -> str:
        """
        Start CAR file download in background.
        
        Args:
            auth_manager: Authenticated manager
            handle: User handle
            data_manager: Data manager instance
            background: Whether to run in background (True) or block (False)
            
        Returns:
            Task ID for tracking download
        """
        # Check if already downloading for this handle
        existing_task_id = self.download_cache.get(handle)
        if existing_task_id:
            existing_task = self.task_manager.get_task(existing_task_id)
            if existing_task and existing_task.status == TaskStatus.RUNNING:
                logger.info(f"CAR download already in progress for {handle}")
                return existing_task_id
        
        def download_car_with_progress(progress_callback=None):
            """Download CAR file with progress tracking."""
            try:
                if progress_callback:
                    progress_callback(0, 100, f"Starting CAR download for {handle}")
                
                # Download CAR file
                car_path = data_manager.download_car(handle)
                
                if progress_callback:
                    progress_callback(50, 100, "CAR file downloaded, processing...")
                
                if not car_path:
                    raise RuntimeError("CAR download failed")
                
                # Get file size for metadata
                file_size = Path(car_path).stat().st_size if Path(car_path).exists() else 0
                
                if progress_callback:
                    progress_callback(100, 100, "CAR download completed")
                
                return {
                    'car_path': str(car_path),
                    'handle': handle,
                    'file_size': file_size,
                    'download_url': f"/download-car?handle={handle}&path={Path(car_path).name}"
                }
                
            except Exception as e:
                logger.error(f"CAR download failed for {handle}: {e}")
                raise
        
        task_id = self.task_manager.create_task(
            TaskType.CAR_DOWNLOAD,
            download_car_with_progress,
            metadata={'handle': handle}
        )
        
        self.download_cache[handle] = task_id
        return task_id
    
    def get_download_status(self, handle: str) -> Optional[BackgroundTask]:
        """Get download status for a handle."""
        task_id = self.download_cache.get(handle)
        if task_id:
            return self.task_manager.get_task(task_id)
        return None

class ParallelHydrationManager:
    """Manager for parallel hydration of multiple users/datasets."""
    
    def __init__(self, task_manager: BackgroundTaskManager, max_concurrent: int = 3):
        self.task_manager = task_manager
        self.max_concurrent = max_concurrent
    
    def start_parallel_hydration(
        self, 
        hydration_jobs: List[Dict[str, Any]]
    ) -> str:
        """
        Start parallel hydration for multiple users/datasets.
        
        Args:
            hydration_jobs: List of hydration job configurations
                Each job should have: {
                    'auth': AuthManager,
                    'items': List[items_to_hydrate],
                    'handle': str,
                    'settings': UserSettings,
                    'metadata': dict (optional)
                }
                
        Returns:
            Task ID for tracking the parallel operation
        """
        def parallel_hydration_worker(progress_callback=None):
            """Execute parallel hydration jobs."""
            total_jobs = len(hydration_jobs)
            completed_jobs = 0
            results = {}
            errors = {}
            
            if progress_callback:
                progress_callback(0, total_jobs, f"Starting {total_jobs} parallel hydration jobs")
            
            # Use ThreadPoolExecutor for parallel processing
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                # Submit all jobs
                future_to_job = {}
                for i, job in enumerate(hydration_jobs):
                    future = executor.submit(self._hydrate_single_job, job, i)
                    future_to_job[future] = job
                
                # Process completed jobs
                for future in as_completed(future_to_job):
                    job = future_to_job[future]
                    handle = job.get('handle', f'job_{len(results)}')
                    
                    try:
                        result = future.result()
                        results[handle] = result
                        logger.info(f"Completed hydration for {handle}")
                        
                    except Exception as e:
                        errors[handle] = str(e)
                        logger.error(f"Failed hydration for {handle}: {e}")
                    
                    completed_jobs += 1
                    if progress_callback:
                        progress_callback(
                            completed_jobs, 
                            total_jobs, 
                            f"Completed {completed_jobs}/{total_jobs} hydration jobs"
                        )
            
            return {
                'completed_jobs': completed_jobs,
                'total_jobs': total_jobs,
                'results': results,
                'errors': errors,
                'success_rate': (len(results) / total_jobs) * 100 if total_jobs > 0 else 0
            }
        
        return self.task_manager.create_task(
            TaskType.PARALLEL_HYDRATION,
            parallel_hydration_worker,
            metadata={'job_count': len(hydration_jobs)}
        )
    
    def _hydrate_single_job(self, job: Dict[str, Any], job_index: int) -> Dict[str, Any]:
        """Execute a single hydration job."""
        auth = job.get('auth')
        items = job.get('items', [])
        handle = job.get('handle', f'job_{job_index}')
        
        start_time = time.time()
        
        try:
            # Use batch processor for optimal performance
            if auth and safe_getattr(auth, 'client', None):
                batch_processor = create_standard_batch_processor(auth.client)
                batch_result = batch_processor.batch_hydrate_engagement(items)
                
                processing_time = time.time() - start_time
                
                return {
                    'handle': handle,
                    'items_processed': len(items),
                    'success_count': batch_result.success_count,
                    'error_count': batch_result.error_count,
                    'success_rate': batch_result.success_rate,
                    'processing_time': processing_time,
                    'batch_results': batch_result
                }
            else:
                raise ValueError(f"No authenticated client available for {handle}")
                
        except Exception as e:
            logger.error(f"Single hydration job failed for {handle}: {e}")
            raise

# Global task manager instance
_task_manager: Optional[BackgroundTaskManager] = None
_car_download_manager: Optional[CARDownloadManager] = None
_parallel_hydration_manager: Optional[ParallelHydrationManager] = None

def get_task_manager() -> BackgroundTaskManager:
    """Get or create global task manager."""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager(max_workers=6)
    return _task_manager

def get_car_download_manager() -> CARDownloadManager:
    """Get or create CAR download manager."""
    global _car_download_manager
    if _car_download_manager is None:
        _car_download_manager = CARDownloadManager(get_task_manager())
    return _car_download_manager

def get_parallel_hydration_manager() -> ParallelHydrationManager:
    """Get or create parallel hydration manager."""
    global _parallel_hydration_manager
    if _parallel_hydration_manager is None:
        _parallel_hydration_manager = ParallelHydrationManager(get_task_manager())
    return _parallel_hydration_manager

def cleanup_managers():
    """Cleanup global managers (for testing/shutdown)."""
    global _task_manager, _car_download_manager, _parallel_hydration_manager
    
    if _task_manager:
        _task_manager.shutdown()
        _task_manager = None
    
    _car_download_manager = None
    _parallel_hydration_manager = None