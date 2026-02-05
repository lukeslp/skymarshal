#!/usr/bin/env python3
"""
BlueSky Vibe Check & Summary Tool (vibe_check_posts.py)

Banner:
- Authenticates with BlueSky API using XAI credentials/endpoints (from bluevibes_ai.py)
- Leverages optimized post fetching logic from bluevibes_db.py with DB caching
- Performs efficient bulk checks to avoid unnecessary API calls
- Stores posts and profiles in a local SQLite DB (.bluevibes.db by default)
- Performs a "vibe check" and/or summary on the user's posts using the XAI model and API
- Outputs results to the console (Rich, accessible)
- CLI usage: python vibe_check_posts.py --handle <bsky_handle> [--db <db_path>] [--max <N>] [--summary] [--vibe] [--force] [--network]
- I/O: CLI args, BlueSky API, local SQLite DB, XAI API, Rich console output

Requirements:
- requests
- rich
- openai (for API calls)
- bluevibes_db.py (for database operations)
- bluevibes_ai.py (for XAI API calls)
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
import threading
import traceback

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich import box
    import requests
    from bluevibes_db import BlueVibesDB, BlueSkyFetcher, authenticate_bsky, format_handle, console
    from bluevibes_ai import query_xai_model, summarize_content
except ImportError as e:
    print(f"Missing required dependencies: {e}")
    print("Please install required packages:")
    print("pip install rich requests openai")
    sys.exit(1)

def vibe_check_posts(db: BlueVibesDB, handle: str, max_posts: int = 5, openai_api_key: str = None) -> None:
    """
    Perform a vibe check on the user's recent posts.
    
    Args:
        db: Database connection
        handle: BlueSky handle to analyze
        max_posts: Maximum number of posts to analyze (most recent)
        openai_api_key: Optional OpenAI API key
    """
    console.print(Panel(f"Vibe Check for @{handle}", border_style="cyan"))
    
    # Get recent posts
    posts = db.get_all_posts(handle, max_posts=max_posts)
    
    if not posts:
        console.print("[yellow]No posts found for this user. Try fetching posts first.[/yellow]")
        return
    
    # Extract text from posts
    texts = db.extract_post_texts(posts)
    
    if not texts:
        console.print("[yellow]No post text content found to analyze.[/yellow]")
        return
    
    # Combine texts
    combined_text = "\n---\n".join(texts[:max_posts])
    
    # Request format for vibe check
    prompt = f"""
    I want you to analyze the following BlueSky posts by @{handle} and give a "vibe check":
    
    {combined_text}
    
    Provide a brief analysis (2-3 paragraphs) of:
    1. The overall tone/vibe of these posts (friendly, informative, promotional, etc.)
    2. Main topics or themes discussed
    3. Writing style and voice
    
    Then provide a short "vibe summary" in 3-5 words.
    """
    
    # Show we're processing
    with console.status("[bold green]Analyzing posts with XAI model...", spinner="dots"):
        try:
            if openai_api_key:
                # Use OpenAI directly if key is provided
                import openai
                openai.api_key = openai_api_key
                
                # Call OpenAI API
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an AI assistant that analyzes posts and provides insightful summaries."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000
                )
                
                result = response.choices[0].message.content
            else:
                # Use XAI model (our wrapper)
                result = query_xai_model(prompt)
        except Exception as e:
            console.print(f"[red]Error during vibe check: {e}[/red]")
            traceback.print_exc()
            return
    
    # Display results
    console.print(Panel(result, title="Vibe Check Result", border_style="green", width=100))

def summarize_posts(db: BlueVibesDB, handle: str, max_posts: int = 10, openai_api_key: str = None) -> None:
    """
    Summarize the user's recent posts.
    
    Args:
        db: Database connection
        handle: BlueSky handle to analyze
        max_posts: Maximum number of posts to summarize
        openai_api_key: Optional OpenAI API key
    """
    console.print(Panel(f"Summarizing Posts for @{handle}", border_style="cyan"))
    
    # Get recent posts
    posts = db.get_all_posts(handle, max_posts=max_posts)
    
    if not posts:
        console.print("[yellow]No posts found for this user. Try fetching posts first.[/yellow]")
        return
    
    # Extract text from posts
    texts = db.extract_post_texts(posts)
    
    if not texts:
        console.print("[yellow]No post text content found to summarize.[/yellow]")
        return
    
    # Combine texts
    combined_text = "\n---\n".join(texts[:max_posts])
    
    # Request format for summary
    prompt = f"""
    Summarize the following {len(texts[:max_posts])} BlueSky posts by @{handle}:
    
    {combined_text}
    
    Provide a concise summary (1-2 paragraphs) of the main ideas, themes, and topics discussed.
    """
    
    # Show we're processing
    with console.status("[bold green]Generating summary with XAI model...", spinner="dots"):
        try:
            if openai_api_key:
                # Use OpenAI directly if key is provided
                import openai
                openai.api_key = openai_api_key
                
                # Call OpenAI API
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an AI assistant that summarizes content concisely and accurately."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500
                )
                
                result = response.choices[0].message.content
            else:
                # Use XAI model (our wrapper)
                result = summarize_content(combined_text)
        except Exception as e:
            console.print(f"[red]Error during summary generation: {e}[/red]")
            traceback.print_exc()
            return
    
    # Display results
    console.print(Panel(result, title="Post Summary", border_style="green", width=100))

def analyze_network_and_posts(db: BlueVibesDB, handle: str, headers: Dict[str, str], force_refresh: bool = False, openai_api_key: str = None) -> None:
    """
    Analyze both network connections and posts to provide comprehensive insights.
    
    Args:
        db: Database connection
        handle: BlueSky handle to analyze
        headers: API headers
        force_refresh: Force refresh data
        openai_api_key: Optional OpenAI API key
    """
    console.print(Panel(f"Comprehensive Analysis for @{handle}", border_style="magenta"))
    
    # Set auth headers on DB class for API access
    db.headers = headers
    
    # Check if we already have cached connections
    cached_followers = db.get_cached_followers(handle)
    cached_following = db.get_cached_following(handle)
    
    # Fetch connections if needed
    if len(cached_followers) == 0 or len(cached_following) == 0 or force_refresh:
        console.print("[cyan]Fetching network connections...[/cyan]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.fields[count]}/{task.fields[total]}"),
            console=console
        ) as progress:
            # Setup progress tracking
            follower_task = progress.add_task(
                f"[cyan]Fetching followers for @{handle}...",
                total=None,
            )
            following_task = progress.add_task(
                f"[cyan]Fetching following for @{handle}...",
                total=None,
            )
            
            def follower_progress_callback(count, total):
                progress.update(follower_task, count=count, total=total)
                
            def following_progress_callback(count, total):
                progress.update(following_task, count=count, total=total)
            
            # Fetch followers with parallel optimization
            db.get_all_followers(handle, progress_callback=follower_progress_callback)
            progress.update(follower_task, completed=True)
            
            # Fetch following with parallel optimization
            db.get_all_following(handle, progress_callback=following_progress_callback)
            progress.update(following_task, completed=True)
            
        followers = db.get_cached_followers(handle)
        following = db.get_cached_following(handle)
        console.print(f"[green]Found {len(followers)} followers and {len(following)} following.[/green]")
    else:
        console.print(f"[green]Using cached data: {len(cached_followers)} followers and {len(cached_following)} following.[/green]")
    
    # Get ratio analysis
    ratio = db.analyze_follower_ratio(handle)
    
    # Create a rich table for the ratio
    ratio_table = Table(title=f"Follower Ratio for @{handle}")
    ratio_table.add_column("Followers", justify="center")
    ratio_table.add_column("Following", justify="center")
    ratio_table.add_column("Ratio", justify="center")
    ratio_table.add_column("Category", justify="center")
    
    ratio_table.add_row(
        f"[cyan]{ratio['follower_count']}[/cyan]",
        f"[cyan]{ratio['following_count']}[/cyan]",
        f"[bold magenta]{ratio['ratio_display']}[/bold magenta]",
        f"[green]{ratio['category']}[/green]"
    )
    
    console.print(ratio_table)
    console.print(f"[dim]{ratio['description']}[/dim]")
    
    # Get network analysis
    network = db.analyze_network(handle)
    
    # Find mutual follows
    console.print(f"\n[bold]Mutual Follows:[/bold] [cyan]{network['mutual_count']}[/cyan] accounts follow @{handle} and are followed back")
    
    # Get posts for analysis
    posts = db.get_all_posts(handle, max_posts=10)
    if not posts:
        console.print("\n[yellow]No posts found for network-content correlation analysis.[/yellow]")
        return
        
    # Extract text from posts
    texts = db.extract_post_texts(posts)
    
    if not texts:
        console.print("\n[yellow]No post text content found for analysis.[/yellow]")
        return
        
    # Display top accounts by ratio
    if network['top_accounts']:
        console.print("\n[bold]Top Accounts in Network:[/bold]")
        top_accts_table = Table()
        top_accts_table.add_column("Handle")
        top_accts_table.add_column("Followers", justify="right")
        top_accts_table.add_column("Following", justify="right")
        top_accts_table.add_column("Ratio", justify="right")
        top_accts_table.add_column("Category")
        
        for acct in network['top_accounts']:
            top_accts_table.add_row(
                f"@{acct['handle']}",
                str(acct['follower_count']),
                str(acct['following_count']),
                f"[bold]{acct['ratio_display']}[/bold]",
                acct['category']
            )
        
        console.print(top_accts_table)
    
    # Combine texts for analysis
    combined_text = "\n---\n".join(texts[:10])
    
    # Generate combined insights with AI
    handles_of_interest = ', '.join([f"@{acct['handle']}" for acct in network['top_accounts'][:3]])
    
    prompt = f"""
    I want you to analyze the following information about @{handle} on BlueSky:
    
    Network Stats:
    - {ratio['follower_count']} followers, {ratio['following_count']} following
    - Follower ratio: {ratio['ratio_display']} ({ratio['category']})
    - {network['mutual_count']} mutual follows
    - Top accounts in their network: {handles_of_interest}
    
    Recent Posts:
    {combined_text}
    
    Based on both their network structure and post content, provide insights on:
    1. Their persona and social role on the platform
    2. Topics they focus on and potential areas of expertise
    3. How their network reflects or contrasts with their content
    4. Suggestions for content that might resonate with their audience
    
    Limit your analysis to 2-3 paragraphs.
    """
    
    # Show we're processing
    with console.status("[bold green]Generating comprehensive insights with XAI model...", spinner="dots"):
        try:
            if openai_api_key:
                # Use OpenAI directly if key is provided
                import openai
                openai.api_key = openai_api_key
                
                # Call OpenAI API
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an AI assistant that provides insightful social media analysis."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000
                )
                
                result = response.choices[0].message.content
            else:
                # Use XAI model (our wrapper)
                result = query_xai_model(prompt)
        except Exception as e:
            console.print(f"[red]Error during comprehensive analysis: {e}[/red]")
            traceback.print_exc()
            return
    
    # Display results
    console.print(Panel(result, title="Comprehensive Analysis", border_style="green", width=100))

def authenticate_with_bluesky(args):
    """Authenticate with BlueSky using command line args or prompts."""
    # If password is provided via args use it, otherwise prompt
    identifier = args.handle
    password = args.pwd

    if not password:
        password = Prompt.ask("Enter your BlueSky password", password=True)
    
    try:
        console.print("[cyan]Authenticating with BlueSky...[/cyan]")
        auth = authenticate_bsky(identifier, password)
        console.print(f"[green]Authenticated as {auth.get('handle')}[/green]")
        return auth["headers"]
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        sys.exit(1)

def run_cli():
    """Main CLI entry point with error handling."""
    try:
        parser = argparse.ArgumentParser(description="BlueSky Vibe Check & Summary Tool")
        parser.add_argument("--handle", help="BlueSky handle to analyze")
        parser.add_argument("--pwd", help="BlueSky password")
        parser.add_argument("--db", default=".bluevibes.db", help="Database file path")
        parser.add_argument("--max", type=int, default=10, help="Maximum posts to fetch/analyze")
        parser.add_argument("--clean", action="store_true", help="Clean out previous posts for this user")
        parser.add_argument("--force", action="store_true", help="Force fetch all posts even if cached")
        parser.add_argument("--summary", action="store_true", help="Generate a summary of posts")
        parser.add_argument("--vibe", action="store_true", help="Perform a vibe check")
        parser.add_argument("--network", action="store_true", help="Analyze network connections")
        parser.add_argument("--comprehensive", action="store_true", help="Perform comprehensive analysis (network + content)")
        parser.add_argument("--openai-key", help="OpenAI API key (optional)")
        
        args = parser.parse_args()
        
        # If no handle is provided, prompt for it
        if not args.handle:
            args.handle = Prompt.ask("Enter BlueSky handle to analyze")
        
        # Initialize database
        db = BlueVibesDB(args.db)
        
        # Authenticate with BlueSky
        headers = authenticate_with_bluesky(args)
        
        # Clean out previous posts if requested
        if args.clean:
            db.clean_user_data(args.handle)
        
        # Create fetcher with authentication headers
        fetcher = BlueSkyFetcher(headers, db)
        
        # Pull posts from BlueSky API
        console.print(f"[cyan]Fetching posts for @{args.handle}...[/cyan]")
        total_added, total_posts = fetcher.pull_all_posts(
            args.handle, 
            max_posts=args.max,
            force_fetch=args.force
        )
        
        console.print(f"[green]Retrieved {total_posts} posts for @{args.handle} (added {total_added} new).[/green]")
        
        # Perform requested analyses
        if args.comprehensive:
            # Comprehensive analysis combines network and content
            analyze_network_and_posts(db, args.handle, headers, force_refresh=args.force, openai_api_key=args.openai_key)
        else:
            # Individual analyses
            if args.network:
                # Set auth headers on DB class for API access
                db.headers = headers
                
                # Fetch connections data
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TextColumn("[cyan]{task.fields[count]}/{task.fields[total]}"),
                    console=console
                ) as progress:
                    # Setup progress tracking
                    follower_task = progress.add_task(
                        f"[cyan]Fetching followers for @{args.handle}...",
                        total=None,
                    )
                    following_task = progress.add_task(
                        f"[cyan]Fetching following for @{args.handle}...",
                        total=None,
                    )
                    
                    def follower_progress_callback(count, total):
                        progress.update(follower_task, count=count, total=total)
                        
                    def following_progress_callback(count, total):
                        progress.update(following_task, count=count, total=total)
                    
                    # Fetch followers with parallel optimization
                    db.get_all_followers(args.handle, progress_callback=follower_progress_callback)
                    progress.update(follower_task, completed=True)
                    
                    # Fetch following with parallel optimization
                    db.get_all_following(args.handle, progress_callback=following_progress_callback)
                    progress.update(following_task, completed=True)
                
                # Get ratio analysis
                ratio = db.analyze_follower_ratio(args.handle)
                
                # Create a rich table for the ratio
                ratio_table = Table(title=f"Follower Ratio for @{args.handle}")
                ratio_table.add_column("Followers", justify="center")
                ratio_table.add_column("Following", justify="center")
                ratio_table.add_column("Ratio", justify="center")
                ratio_table.add_column("Category", justify="center")
                
                ratio_table.add_row(
                    f"[cyan]{ratio['follower_count']}[/cyan]",
                    f"[cyan]{ratio['following_count']}[/cyan]",
                    f"[bold magenta]{ratio['ratio_display']}[/bold magenta]",
                    f"[green]{ratio['category']}[/green]"
                )
                
                console.print(ratio_table)
                console.print(f"[dim]{ratio['description']}[/dim]")
                
                # Get network analysis
                network = db.analyze_network(args.handle)
                
                # Find mutual follows
                console.print(f"\n[bold]Mutual Follows:[/bold] [cyan]{network['mutual_count']}[/cyan] accounts you follow who also follow you")
                
                # Display top accounts by ratio
                if network['top_accounts']:
                    console.print("\n[bold]Top Accounts by Follower Ratio:[/bold]")
                    top_accts_table = Table()
                    top_accts_table.add_column("Handle")
                    top_accts_table.add_column("Followers", justify="right")
                    top_accts_table.add_column("Following", justify="right")
                    top_accts_table.add_column("Ratio", justify="right")
                    top_accts_table.add_column("Category")
                    
                    for acct in network['top_accounts']:
                        top_accts_table.add_row(
                            f"@{acct['handle']}",
                            str(acct['follower_count']),
                            str(acct['following_count']),
                            f"[bold]{acct['ratio_display']}[/bold]",
                            acct['category']
                        )
                    
                    console.print(top_accts_table)
            
            if args.vibe:
                vibe_check_posts(db, args.handle, max_posts=args.max, openai_api_key=args.openai_key)
                
            if args.summary:
                summarize_posts(db, args.handle, max_posts=args.max, openai_api_key=args.openai_key)
        
        # If no specific action was requested, show a help message
        if not any([args.vibe, args.summary, args.network, args.comprehensive]):
            console.print("[yellow]No analysis action specified. Use --vibe, --summary, --network, or --comprehensive.[/yellow]")
            console.print("Examples:")
            console.print("  python vibe_check_posts.py --handle USER --vibe")
            console.print("  python vibe_check_posts.py --handle USER --summary --max 20")
            console.print("  python vibe_check_posts.py --handle USER --network")
            console.print("  python vibe_check_posts.py --handle USER --comprehensive")
        
        # Close database connection
        db.conn.close()
        
    except ImportError as e:
        console.print(f"[red]ERROR: Missing required dependencies: {e}[/red]")
        console.print("[red]Please install required packages:  pip install rich requests openai[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]ERROR: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_cli() 