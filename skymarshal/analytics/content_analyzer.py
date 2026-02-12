"""
Content Analyzer Module

This module provides LLM-powered content analysis capabilities for Bluesky posts.
It integrates functionality from the standalone vibe_check_posts.py tool.

Features:
- LLM-powered content analysis and vibe checking
- Post summarization and theme extraction
- Sentiment analysis and tone detection
- Content categorization and insights
- Integration with XAI/Grok models
"""

import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
import requests
import os

from ..models import console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn


class ContentAnalyzer:
    """
    Analyzes Bluesky content using AI models for insights and categorization.
    
    This class provides LLM-powered content analysis capabilities including:
    - Vibe checking and tone analysis
    - Content summarization
    - Theme and topic extraction
    - Sentiment analysis
    - Content categorization
    """
    
    def __init__(self, auth_manager, api_key: str = None):
        """
        Initialize the ContentAnalyzer.
        
        Args:
            auth_manager: Authenticated Bluesky client manager
            api_key: Optional API key for AI services (defaults to environment variable)
        """
        self.auth_manager = auth_manager
        self.client = auth_manager.client
        
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv('XAI_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            console.print("[yellow]⚠️ No API key provided. AI analysis features will be limited.[/yellow]")
        
        # API endpoints
        self.xai_endpoint = "https://api.x.ai/v1/chat/completions"
        self.openai_endpoint = "https://api.openai.com/v1/chat/completions"
    
    def analyze_content_vibe(self, posts: List[Dict], max_posts: int = 10) -> Dict[str, Any]:
        """
        Perform a vibe check analysis on a collection of posts.
        
        Args:
            posts: List of post dictionaries
            max_posts: Maximum number of posts to analyze
            
        Returns:
            Dict: Vibe analysis results
        """
        if not posts:
            return {'error': 'No posts provided for analysis'}
        
        console.print(f"[blue]🔍 Analyzing vibe for {min(len(posts), max_posts)} posts...[/blue]")
        
        # Extract text content from posts
        texts = []
        for post in posts[:max_posts]:
            text = post.get('text', '').strip()
            if text:
                texts.append(text)
        
        if not texts:
            return {'error': 'No text content found in posts'}
        
        # Combine texts for analysis
        combined_text = "\n---\n".join(texts)
        
        # Create vibe check prompt
        prompt = f"""
        I want you to analyze the following Bluesky posts and provide a comprehensive "vibe check":
        
        {combined_text}
        
        Please provide:
        1. Overall tone/vibe (friendly, informative, promotional, casual, professional, etc.)
        2. Main topics or themes discussed
        3. Writing style and voice characteristics
        4. Content quality assessment
        5. Engagement potential analysis
        6. A short "vibe summary" in 3-5 words
        
        Format your response as JSON with the following structure:
        {{
            "tone": "description of overall tone",
            "themes": ["theme1", "theme2", "theme3"],
            "style": "description of writing style",
            "quality": "assessment of content quality",
            "engagement_potential": "assessment of engagement potential",
            "vibe_summary": "3-5 word summary",
            "insights": "additional insights or observations"
        }}
        """
        
        # Call AI model
        try:
            response = self._call_ai_model(prompt)
            if response:
                # Try to parse JSON response
                try:
                    analysis = json.loads(response)
                    return {
                        'success': True,
                        'analysis': analysis,
                        'posts_analyzed': len(texts),
                        'timestamp': datetime.now().isoformat()
                    }
                except json.JSONDecodeError:
                    # If JSON parsing fails, return raw response
                    return {
                        'success': True,
                        'analysis': {'raw_response': response},
                        'posts_analyzed': len(texts),
                        'timestamp': datetime.now().isoformat()
                    }
            else:
                return {'error': 'Failed to get AI response'}
                
        except Exception as e:
            console.print(f"[red]❌ Error in vibe analysis: {str(e)}[/red]")
            return {'error': f'Analysis failed: {str(e)}'}
    
    def summarize_content(self, posts: List[Dict], max_posts: int = 20) -> Dict[str, Any]:
        """
        Generate a summary of content themes and topics.
        
        Args:
            posts: List of post dictionaries
            max_posts: Maximum number of posts to analyze
            
        Returns:
            Dict: Content summary results
        """
        if not posts:
            return {'error': 'No posts provided for summarization'}
        
        console.print(f"[blue]📝 Summarizing content from {min(len(posts), max_posts)} posts...[/blue]")
        
        # Extract text content
        texts = []
        for post in posts[:max_posts]:
            text = post.get('text', '').strip()
            if text:
                texts.append(text)
        
        if not texts:
            return {'error': 'No text content found in posts'}
        
        # Combine texts
        combined_text = "\n---\n".join(texts)
        
        # Create summarization prompt
        prompt = f"""
        Please analyze and summarize the following Bluesky posts:
        
        {combined_text}
        
        Provide a comprehensive summary including:
        1. Main topics and themes discussed
        2. Content categories (personal, professional, news, opinions, etc.)
        3. Key insights or patterns
        4. Content frequency and consistency
        5. Overall content strategy assessment
        
        Format your response as JSON:
        {{
            "main_topics": ["topic1", "topic2", "topic3"],
            "content_categories": ["category1", "category2"],
            "key_insights": ["insight1", "insight2"],
            "content_frequency": "assessment of posting frequency",
            "consistency": "assessment of content consistency",
            "strategy": "overall content strategy assessment",
            "summary": "brief overall summary"
        }}
        """
        
        try:
            response = self._call_ai_model(prompt)
            if response:
                try:
                    summary = json.loads(response)
                    return {
                        'success': True,
                        'summary': summary,
                        'posts_analyzed': len(texts),
                        'timestamp': datetime.now().isoformat()
                    }
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'summary': {'raw_response': response},
                        'posts_analyzed': len(texts),
                        'timestamp': datetime.now().isoformat()
                    }
            else:
                return {'error': 'Failed to get AI response'}
                
        except Exception as e:
            console.print(f"[red]❌ Error in content summarization: {str(e)}[/red]")
            return {'error': f'Summarization failed: {str(e)}'}
    
    def analyze_sentiment(self, posts: List[Dict], max_posts: int = 15) -> Dict[str, Any]:
        """
        Analyze sentiment and emotional tone of posts.
        
        Args:
            posts: List of post dictionaries
            max_posts: Maximum number of posts to analyze
            
        Returns:
            Dict: Sentiment analysis results
        """
        if not posts:
            return {'error': 'No posts provided for sentiment analysis'}
        
        console.print(f"[blue]😊 Analyzing sentiment for {min(len(posts), max_posts)} posts...[/blue]")
        
        # Extract text content
        texts = []
        for post in posts[:max_posts]:
            text = post.get('text', '').strip()
            if text:
                texts.append(text)
        
        if not texts:
            return {'error': 'No text content found in posts'}
        
        # Combine texts
        combined_text = "\n---\n".join(texts)
        
        # Create sentiment analysis prompt
        prompt = f"""
        Analyze the sentiment and emotional tone of the following Bluesky posts:
        
        {combined_text}
        
        Provide a detailed sentiment analysis including:
        1. Overall emotional tone (positive, negative, neutral, mixed)
        2. Specific emotions detected (joy, anger, sadness, excitement, etc.)
        3. Sentiment distribution across posts
        4. Language patterns that indicate sentiment
        5. Recommendations for tone adjustment if needed
        
        Format your response as JSON:
        {{
            "overall_tone": "positive/negative/neutral/mixed",
            "emotions": ["emotion1", "emotion2", "emotion3"],
            "sentiment_distribution": "description of sentiment spread",
            "language_patterns": "description of language patterns",
            "recommendations": "tone adjustment recommendations",
            "confidence": "confidence level in analysis"
        }}
        """
        
        try:
            response = self._call_ai_model(prompt)
            if response:
                try:
                    sentiment = json.loads(response)
                    return {
                        'success': True,
                        'sentiment': sentiment,
                        'posts_analyzed': len(texts),
                        'timestamp': datetime.now().isoformat()
                    }
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'sentiment': {'raw_response': response},
                        'posts_analyzed': len(texts),
                        'timestamp': datetime.now().isoformat()
                    }
            else:
                return {'error': 'Failed to get AI response'}
                
        except Exception as e:
            console.print(f"[red]❌ Error in sentiment analysis: {str(e)}[/red]")
            return {'error': f'Sentiment analysis failed: {str(e)}'}
    
    def categorize_content(self, posts: List[Dict], max_posts: int = 20) -> Dict[str, Any]:
        """
        Categorize posts by type, topic, and purpose.
        
        Args:
            posts: List of post dictionaries
            max_posts: Maximum number of posts to analyze
            
        Returns:
            Dict: Content categorization results
        """
        if not posts:
            return {'error': 'No posts provided for categorization'}
        
        console.print(f"[blue]📂 Categorizing {min(len(posts), max_posts)} posts...[/blue]")
        
        # Extract text content
        texts = []
        for post in posts[:max_posts]:
            text = post.get('text', '').strip()
            if text:
                texts.append(text)
        
        if not texts:
            return {'error': 'No text content found in posts'}
        
        # Combine texts
        combined_text = "\n---\n".join(texts)
        
        # Create categorization prompt
        prompt = f"""
        Categorize the following Bluesky posts by type, topic, and purpose:
        
        {combined_text}
        
        Provide detailed categorization including:
        1. Post types (personal update, news, opinion, question, promotion, etc.)
        2. Topic categories (technology, politics, entertainment, lifestyle, etc.)
        3. Purpose (informational, promotional, conversational, etc.)
        4. Content format (text-only, with links, with hashtags, etc.)
        5. Engagement strategy (questions, calls-to-action, etc.)
        
        Format your response as JSON:
        {{
            "post_types": ["type1", "type2", "type3"],
            "topic_categories": ["topic1", "topic2", "topic3"],
            "purposes": ["purpose1", "purpose2"],
            "formats": ["format1", "format2"],
            "engagement_strategies": ["strategy1", "strategy2"],
            "content_balance": "assessment of content variety",
            "recommendations": "suggestions for content improvement"
        }}
        """
        
        try:
            response = self._call_ai_model(prompt)
            if response:
                try:
                    categories = json.loads(response)
                    return {
                        'success': True,
                        'categories': categories,
                        'posts_analyzed': len(texts),
                        'timestamp': datetime.now().isoformat()
                    }
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'categories': {'raw_response': response},
                        'posts_analyzed': len(texts),
                        'timestamp': datetime.now().isoformat()
                    }
            else:
                return {'error': 'Failed to get AI response'}
                
        except Exception as e:
            console.print(f"[red]❌ Error in content categorization: {str(e)}[/red]")
            return {'error': f'Categorization failed: {str(e)}'}
    
    def _call_ai_model(self, prompt: str) -> Optional[str]:
        """
        Call AI model (XAI/Grok or OpenAI) with the given prompt.
        
        Args:
            prompt: The prompt to send to the AI model
            
        Returns:
            Optional[str]: AI response or None if failed
        """
        if not self.api_key:
            console.print("[yellow]⚠️ No API key available for AI analysis[/yellow]")
            return None
        
        # Try XAI/Grok first, then OpenAI
        for endpoint, model in [(self.xai_endpoint, "grok-beta"), (self.openai_endpoint, "gpt-3.5-turbo")]:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.7
                }
                
                response = requests.post(endpoint, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content']
                
            except Exception as e:
                console.print(f"[yellow]⚠️ Error with {model}: {str(e)}[/yellow]")
                continue
        
        return None
    
    def display_analysis_results(self, analysis: Dict[str, Any]):
        """Display analysis results in a formatted panel."""
        
        if 'error' in analysis:
            console.print(f"[red]❌ {analysis['error']}[/red]")
            return
        
        if not analysis.get('success'):
            console.print("[red]❌ Analysis failed[/red]")
            return
        
        # Display based on analysis type
        if 'analysis' in analysis:
            # Vibe analysis
            vibe_data = analysis['analysis']
            if isinstance(vibe_data, dict) and 'raw_response' not in vibe_data:
                content = f"""
Tone: {vibe_data.get('tone', 'N/A')}
Themes: {', '.join(vibe_data.get('themes', []))}
Style: {vibe_data.get('style', 'N/A')}
Quality: {vibe_data.get('quality', 'N/A')}
Vibe Summary: {vibe_data.get('vibe_summary', 'N/A')}
                """
            else:
                content = str(vibe_data)
            
            console.print(Panel(content, title="Vibe Analysis", border_style="cyan"))
        
        elif 'summary' in analysis:
            # Content summary
            summary_data = analysis['summary']
            if isinstance(summary_data, dict) and 'raw_response' not in summary_data:
                content = f"""
Main Topics: {', '.join(summary_data.get('main_topics', []))}
Categories: {', '.join(summary_data.get('content_categories', []))}
Key Insights: {', '.join(summary_data.get('key_insights', []))}
Strategy: {summary_data.get('strategy', 'N/A')}
                """
            else:
                content = str(summary_data)
            
            console.print(Panel(content, title="Content Summary", border_style="green"))
        
        elif 'sentiment' in analysis:
            # Sentiment analysis
            sentiment_data = analysis['sentiment']
            if isinstance(sentiment_data, dict) and 'raw_response' not in sentiment_data:
                content = f"""
Overall Tone: {sentiment_data.get('overall_tone', 'N/A')}
Emotions: {', '.join(sentiment_data.get('emotions', []))}
Distribution: {sentiment_data.get('sentiment_distribution', 'N/A')}
Recommendations: {sentiment_data.get('recommendations', 'N/A')}
                """
            else:
                content = str(sentiment_data)
            
            console.print(Panel(content, title="Sentiment Analysis", border_style="yellow"))
        
        elif 'categories' in analysis:
            # Content categorization
            category_data = analysis['categories']
            if isinstance(category_data, dict) and 'raw_response' not in category_data:
                content = f"""
Post Types: {', '.join(category_data.get('post_types', []))}
Topics: {', '.join(category_data.get('topic_categories', []))}
Purposes: {', '.join(category_data.get('purposes', []))}
Formats: {', '.join(category_data.get('formats', []))}
Balance: {category_data.get('content_balance', 'N/A')}
                """
            else:
                content = str(category_data)
            
            console.print(Panel(content, title="Content Categorization", border_style="magenta"))
    
    async def run_complete_analysis(self, posts: List[Dict], analysis_types: List[str] = None) -> Dict[str, Any]:
        """
        Run complete content analysis with multiple analysis types.
        
        Args:
            posts: List of post dictionaries to analyze
            analysis_types: List of analysis types to run ('vibe', 'summary', 'sentiment', 'categorize')
            
        Returns:
            Dict: Complete analysis results
        """
        if analysis_types is None:
            analysis_types = ['vibe', 'summary', 'sentiment', 'categorize']
        
        console.print(f"[bold blue]🚀 Starting complete content analysis[/bold blue]")
        
        results = {
            'posts_analyzed': len(posts),
            'timestamp': datetime.now().isoformat(),
            'analyses': {}
        }
        
        # Run each analysis type
        for analysis_type in analysis_types:
            console.print(f"[blue]🔍 Running {analysis_type} analysis...[/blue]")
            
            if analysis_type == 'vibe':
                result = self.analyze_content_vibe(posts)
            elif analysis_type == 'summary':
                result = self.summarize_content(posts)
            elif analysis_type == 'sentiment':
                result = self.analyze_sentiment(posts)
            elif analysis_type == 'categorize':
                result = self.categorize_content(posts)
            else:
                console.print(f"[yellow]⚠️ Unknown analysis type: {analysis_type}[/yellow]")
                continue
            
            results['analyses'][analysis_type] = result
            
            # Display results
            if result.get('success'):
                self.display_analysis_results(result)
            else:
                console.print(f"[red]❌ {analysis_type} analysis failed: {result.get('error', 'Unknown error')}[/red]")
        
        return results