#!/usr/bin/env python3
"""
Demonstration of the optimized batch processing system showing performance improvements.

This script compares the old individual processing approach vs the new 25-item batching
to demonstrate the significant API efficiency improvements.
"""
from __future__ import annotations

import time
from typing import List, Dict, Any
from dataclasses import dataclass

from batch_processor import create_standard_batch_processor, BatchConfig, BatchStrategy
from utils import HydrationConfig

@dataclass
class MockItem:
    """Mock content item for testing."""
    uri: str
    content_type: str = "post"
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    
    def update_engagement_score(self):
        """Mock engagement score update."""
        pass

def simulate_old_individual_processing(items: List[MockItem]) -> Dict[str, float]:
    """
    Simulate the old approach: individual API calls for each item.
    
    This is what was happening in app.py, web_simple.py, and hydrate_last_500.py
    before the batch optimization.
    """
    start_time = time.time()
    
    print(f"🐌 OLD APPROACH: Processing {len(items)} items individually...")
    api_calls = 0
    
    for i, item in enumerate(items):
        # Simulate individual API call delay (typical 0.2-0.4s per request)
        time.sleep(0.05)  # Reduced for demo purposes
        api_calls += 1
        
        # Simulate setting engagement data
        item.like_count = i % 10
        item.repost_count = i % 5
        item.reply_count = i % 3
        
        if (i + 1) % 10 == 0:
            print(f"   Processed {i + 1}/{len(items)} items ({api_calls} API calls)")
    
    processing_time = time.time() - start_time
    
    return {
        "processing_time": processing_time,
        "api_calls": api_calls,
        "items_processed": len(items),
        "calls_per_second": api_calls / processing_time if processing_time > 0 else 0
    }

def simulate_new_batch_processing(items: List[MockItem]) -> Dict[str, float]:
    """
    Simulate the new approach: 25-item batches with single API calls.
    
    This is what the new batch_processor.py system provides.
    """
    start_time = time.time()
    
    print(f"🚀 NEW APPROACH: Processing {len(items)} items in 25-item batches...")
    
    # Create standard batch processor (25 items per batch)
    config = BatchConfig(strategy=BatchStrategy.STANDARD, delay_between_batches=0.2)
    
    def mock_batch_processor(batch: List[MockItem]) -> List[MockItem]:
        """Mock processing function that simulates single API call for batch."""
        # Simulate single API call delay for entire batch
        time.sleep(0.05)  # Same delay as individual, but for entire batch
        
        # Update all items in batch
        for i, item in enumerate(batch):
            item.like_count = i % 10
            item.repost_count = i % 5
            item.reply_count = i % 3
        
        return batch
    
    # Process in batches
    api_calls = 0
    batch_size = config.batch_size
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        mock_batch_processor(batch)
        api_calls += 1
        
        print(f"   Processed batch {api_calls}: {len(batch)} items "
              f"(total: {min(i + batch_size, len(items))}/{len(items)})")
        
        # Rate limiting delay between batches
        if i + batch_size < len(items):
            time.sleep(config.delay_between_batches)
    
    processing_time = time.time() - start_time
    
    return {
        "processing_time": processing_time,
        "api_calls": api_calls,
        "items_processed": len(items),
        "calls_per_second": api_calls / processing_time if processing_time > 0 else 0
    }

def run_performance_comparison():
    """Run a comprehensive performance comparison."""
    
    print("=" * 70)
    print("🔥 BLUESKY API BATCH PROCESSING PERFORMANCE COMPARISON")
    print("=" * 70)
    print()
    
    # Test different dataset sizes
    test_sizes = [25, 50, 100, 250]
    
    for size in test_sizes:
        print(f"\n📊 TESTING WITH {size} ITEMS")
        print("-" * 50)
        
        # Create test items
        items_old = [MockItem(uri=f"at://did:plc:test/post/{i}") for i in range(size)]
        items_new = [MockItem(uri=f"at://did:plc:test/post/{i}") for i in range(size)]
        
        # Test old approach
        old_results = simulate_old_individual_processing(items_old)
        
        print()
        
        # Test new approach
        new_results = simulate_new_batch_processing(items_new)
        
        # Calculate improvements
        time_improvement = (old_results["processing_time"] - new_results["processing_time"]) / old_results["processing_time"] * 100
        api_call_reduction = (old_results["api_calls"] - new_results["api_calls"]) / old_results["api_calls"] * 100
        throughput_improvement = (new_results["calls_per_second"] - old_results["calls_per_second"]) / old_results["calls_per_second"] * 100
        
        print(f"\n📈 RESULTS SUMMARY:")
        print(f"   Old approach: {old_results['processing_time']:.2f}s, {old_results['api_calls']} API calls")
        print(f"   New approach: {new_results['processing_time']:.2f}s, {new_results['api_calls']} API calls")
        print(f"   ⚡ Time saved: {time_improvement:.1f}%")
        print(f"   📉 API calls reduced: {api_call_reduction:.1f}%")
        print(f"   🚀 Throughput improvement: {throughput_improvement:.1f}%")
        
        if size == 250:  # Show detailed benefits for larger dataset
            print(f"\n💡 FOR {size} ITEMS:")
            print(f"   • Reduced API calls from {old_results['api_calls']} to {new_results['api_calls']}")
            print(f"   • Saved {old_results['processing_time'] - new_results['processing_time']:.2f} seconds")
            print(f"   • Reduced server load by {api_call_reduction:.0f}%")
            print(f"   • Better rate limit compliance")
            print(f"   • More predictable performance")

def show_batch_strategies():
    """Demonstrate different batching strategies."""
    
    print("\n" + "=" * 70)
    print("⚙️  AVAILABLE BATCH PROCESSING STRATEGIES")
    print("=" * 70)
    
    strategies = [
        (BatchStrategy.STANDARD, "Standard", "Optimal for getPosts API (25 items)"),
        (BatchStrategy.CONSERVATIVE, "Conservative", "Rate-limited scenarios (20 items)"),
        (BatchStrategy.LARGE_PAGINATION, "Large Pagination", "For pagination endpoints (100 items)"),
        (BatchStrategy.SMALL, "Small/Testing", "Testing or slow endpoints (10 items)")
    ]
    
    for strategy, name, description in strategies:
        config = BatchConfig(strategy=strategy)
        print(f"\n🔧 {name}:")
        print(f"   • Batch size: {config.batch_size} items")
        print(f"   • Use case: {description}")
        print(f"   • Delay: {config.delay_between_batches}s between batches")
        print(f"   • Max retries: {config.max_retries}")

if __name__ == "__main__":
    print("Starting batch processing performance demonstration...")
    print("This compares individual processing vs 25-item batching.")
    print()
    
    run_performance_comparison()
    show_batch_strategies()
    
    print("\n" + "=" * 70)
    print("✅ OPTIMIZATION COMPLETE!")
    print("=" * 70)
    print()
    print("🎯 Key Benefits of 25-Item Batching:")
    print("   • Up to 96% reduction in API calls (250 items: 250 → 10 calls)")
    print("   • Faster processing with better rate limit compliance")
    print("   • Consistent performance regardless of dataset size")
    print("   • Optimal use of Bluesky's getPosts API (max 25 URIs)")
    print("   • Automatic retry logic with exponential backoff")
    print("   • Configurable strategies for different scenarios")
    print()
    print("🔄 Updated Files:")
    print("   • batch_processor.py - New optimized batch processing system")
    print("   • improved_hydration.py - Updated to use 25-item batching")
    print("   • hydration_service.py - Integrated batch processors")
    print("   • utils.py - Enhanced with batch processing support")
    print()
    print("Ready for production use! 🚀")