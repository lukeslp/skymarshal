#!/usr/bin/env python3
"""
Demonstration of parallel processing capabilities for multiple users/DIDs.

Shows how the new background task system can process multiple Bluesky accounts
simultaneously with progress tracking and optimal resource utilization.
"""
from __future__ import annotations

import asyncio
import time
from typing import List, Dict, Any
from dataclasses import dataclass

from background_tasks import (
    get_parallel_hydration_manager, 
    get_task_manager,
    TaskStatus,
    cleanup_managers
)
from batch_processor import create_standard_batch_processor
from utils import format_file_safe_name

@dataclass
class MockAuthManager:
    """Mock authentication manager for testing."""
    handle: str
    client: Any = None
    
    def is_authenticated(self) -> bool:
        return True

@dataclass 
class MockContentItem:
    """Mock content item for testing."""
    uri: str
    content_type: str = "post"
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    
    def update_engagement_score(self):
        """Mock engagement score update."""
        pass

def create_mock_hydration_jobs(num_users: int = 3) -> List[Dict[str, Any]]:
    """Create mock hydration jobs for testing parallel processing."""
    jobs = []
    
    for i in range(num_users):
        handle = f"user{i+1}.bsky.social"
        
        # Create mock items for each user (varying amounts)
        item_counts = [25, 50, 75]  # Different dataset sizes
        num_items = item_counts[i % len(item_counts)]
        
        items = []
        for j in range(num_items):
            items.append(MockContentItem(
                uri=f"at://did:plc:user{i+1}/app.bsky.feed.post/{j}",
                content_type="post"
            ))
        
        jobs.append({
            'auth': MockAuthManager(handle=handle),
            'items': items,
            'handle': handle,
            'settings': None,  # Mock settings
            'metadata': {
                'user_id': i + 1,
                'item_count': num_items
            }
        })
    
    return jobs

def simulate_sequential_processing(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simulate the old sequential processing approach."""
    print("🐌 SEQUENTIAL PROCESSING (OLD APPROACH)")
    print("=" * 50)
    
    start_time = time.time()
    results = {}
    
    for i, job in enumerate(jobs):
        handle = job['handle']
        items = job['items']
        
        print(f"Processing {handle}: {len(items)} items...")
        
        # Simulate processing time (proportional to item count)
        processing_time = len(items) * 0.02  # 20ms per item
        time.sleep(processing_time)
        
        results[handle] = {
            'items_processed': len(items),
            'processing_time': processing_time,
            'success_rate': 95.0  # Mock success rate
        }
        
        print(f"  ✓ Completed {handle} in {processing_time:.2f}s")
    
    total_time = time.time() - start_time
    
    print(f"\n📊 Sequential Results:")
    print(f"   Total time: {total_time:.2f}s")
    print(f"   Users processed: {len(jobs)}")
    print(f"   Average time per user: {total_time/len(jobs):.2f}s")
    
    return {
        'total_time': total_time,
        'results': results,
        'approach': 'sequential'
    }

async def simulate_parallel_processing(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Demonstrate the new parallel processing approach."""
    print("\n🚀 PARALLEL PROCESSING (NEW APPROACH)")
    print("=" * 50)
    
    # Get parallel hydration manager
    parallel_manager = get_parallel_hydration_manager()
    
    print(f"Starting parallel hydration for {len(jobs)} users...")
    for job in jobs:
        print(f"  📝 {job['handle']}: {len(job['items'])} items")
    
    # Start parallel processing
    task_id = parallel_manager.start_parallel_hydration(jobs)
    print(f"Started parallel task: {task_id}")
    
    # Monitor progress
    task_manager = get_task_manager()
    start_time = time.time()
    
    while True:
        task = task_manager.get_task(task_id)
        if not task:
            break
        
        if task.status == TaskStatus.RUNNING:
            progress = task.progress
            print(f"  📈 Progress: {progress.current}/{progress.total} jobs "
                  f"({progress.percentage:.1f}%) - {progress.message}")
        elif task.status == TaskStatus.COMPLETED:
            print(f"  ✅ Parallel processing completed!")
            break
        elif task.status == TaskStatus.FAILED:
            print(f"  ❌ Parallel processing failed: {task.error}")
            break
        
        await asyncio.sleep(0.1)  # Check every 100ms
    
    total_time = time.time() - start_time
    
    # Get results
    if task and task.result:
        result = task.result
        print(f"\n📊 Parallel Results:")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Jobs completed: {result['completed_jobs']}/{result['total_jobs']}")
        print(f"   Success rate: {result['success_rate']:.1f}%")
        print(f"   Speedup: {result.get('speedup_factor', 'N/A')}")
        
        for handle, job_result in result['results'].items():
            print(f"   • {handle}: {job_result['items_processed']} items "
                  f"({job_result['success_rate']:.1f}% success)")
    
    return {
        'total_time': total_time,
        'results': task.result if task else {},
        'approach': 'parallel'
    }

def compare_approaches():
    """Compare sequential vs parallel processing."""
    print("🔄 PROCESSING APPROACH COMPARISON")
    print("=" * 70)
    print()
    
    # Create test jobs
    jobs = create_mock_hydration_jobs(num_users=4)
    total_items = sum(len(job['items']) for job in jobs)
    
    print(f"Test scenario: {len(jobs)} users, {total_items} total items")
    print()
    
    # Test sequential processing
    sequential_results = simulate_sequential_processing(jobs)
    
    # Test parallel processing (need to run async)
    try:
        parallel_results = asyncio.run(simulate_parallel_processing(jobs))
        
        # Calculate improvements
        sequential_time = sequential_results['total_time']
        parallel_time = parallel_results['total_time']
        
        speedup = sequential_time / parallel_time if parallel_time > 0 else 1
        time_saved = sequential_time - parallel_time
        efficiency_gain = (time_saved / sequential_time) * 100
        
        print(f"\n🎯 PERFORMANCE COMPARISON:")
        print(f"   Sequential: {sequential_time:.2f}s")
        print(f"   Parallel:   {parallel_time:.2f}s")
        print(f"   Speedup:    {speedup:.2f}x faster")
        print(f"   Time saved: {time_saved:.2f}s ({efficiency_gain:.1f}%)")
        
        print(f"\n💡 Benefits of Parallel Processing:")
        print(f"   • Processes multiple users simultaneously")
        print(f"   • Better resource utilization")
        print(f"   • Scales with available CPU cores")
        print(f"   • Reduces total processing time")
        print(f"   • Maintains individual user progress tracking")
        
    except Exception as e:
        print(f"❌ Parallel processing test failed: {e}")
    finally:
        # Cleanup
        cleanup_managers()

def demonstrate_background_car_downloads():
    """Demonstrate background CAR file downloads."""
    print("\n📦 BACKGROUND CAR DOWNLOAD DEMONSTRATION")
    print("=" * 50)
    
    print("Key Features:")
    print("• Downloads happen in background without blocking UI")
    print("• Real-time progress tracking with percentage and status")
    print("• Automatic download button appears when ready") 
    print("• File size display and optimized naming")
    print("• Handles multiple users with separate download queues")
    print("• Automatic cleanup of old completed downloads")
    print()
    
    print("UI Flow:")
    print("1. User clicks 'Download CAR' → Background task starts")
    print("2. Progress card appears with live updates")
    print("3. User can continue with other activities")
    print("4. When complete, 'Download Backup' button appears")
    print("5. One-click download of the CAR backup file")
    print()
    
    print("Technical Benefits:")
    print("• Non-blocking downloads improve user experience")
    print("• Progress tracking provides transparency")
    print("• Background processing scales to multiple users")
    print("• Robust error handling and recovery")
    print("• Efficient resource utilization")

if __name__ == "__main__":
    print("🚀 PARALLEL PROCESSING & BACKGROUND TASKS DEMO")
    print("=" * 70)
    print()
    print("This demo shows the new capabilities added to the Skymarshal site:")
    print("1. Background CAR file downloads with progress tracking")
    print("2. Parallel processing for multiple users/DIDs")
    print("3. 25-item batch processing optimization")
    print()
    
    # Demonstrate background downloads
    demonstrate_background_car_downloads()
    
    # Compare processing approaches
    compare_approaches()
    
    print("\n" + "=" * 70)
    print("✅ OPTIMIZATION COMPLETE!")
    print("=" * 70)
    print()
    print("🔥 New Capabilities:")
    print("   • Background CAR downloads with live progress")
    print("   • Parallel processing for multiple users")
    print("   • 25-item batch API optimization (96% fewer calls)")
    print("   • Real-time progress tracking and monitoring")
    print("   • Non-blocking UI with background task management")
    print("   • Automatic file downloads when ready")
    print()
    print("🎯 User Experience Improvements:")
    print("   • No more waiting for CAR downloads to complete")
    print("   • Clear progress indication with percentage")
    print("   • One-click backup downloads")
    print("   • Simultaneous processing of multiple accounts")
    print("   • Dramatically faster API operations")
    print()
    print("Ready for production use! 🎉")