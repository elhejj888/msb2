import tkinter as tk
from tkinter import filedialog
import os
from datetime import datetime
from typing import Dict, Any
from .models import Tweet

def select_media():
    """
    Open file dialog to select media file
    
    Returns:
    - str: Path to selected media or None if canceled
    """
    root = tk.Tk()
    root.withdraw()
    
    file_path = filedialog.askopenfilename(
        title="Select Media",
        filetypes=[
            ("Image files", "*.jpg *.jpeg *.png *.gif"),
            ("Video files", "*.mp4 *.mov *.avi"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    
    return file_path if file_path else None

def format_tweet_response(response_data: Dict[str, Any]) -> Tweet:
    """
    Format raw X/Twitter API response into a standardized Tweet object
    
    Args:
        response_data: Raw response data from X/Twitter API
        
    Returns:
        Tweet: Standardized tweet object
        
    Example Input:
        {
            "data": {
                "id": "12345",
                "text": "Hello world!",
                "created_at": "2023-01-01T12:00:00Z",
                "public_metrics": {
                    "retweet_count": 10,
                    "reply_count": 5,
                    "like_count": 20,
                    "quote_count": 3
                },
                "author_id": "67890",
                "attachments": {
                    "media_keys": ["3_1234567890"]
                }
            },
            "includes": {
                "users": [{
                    "id": "67890",
                    "name": "John Doe",
                    "username": "johndoe"
                }],
                "media": [{
                    "media_key": "3_1234567890",
                    "type": "photo",
                    "url": "https://example.com/image.jpg"
                }]
            }
        }
    """
    tweet_data = response_data.get('data', {})
    includes = response_data.get('includes', {})
    
    # Extract basic tweet information
    tweet_id = tweet_data.get('id')
    text = tweet_data.get('text', '')
    created_at = tweet_data.get('created_at', '')
    
    # Build URL
    username = None
    if 'users' in includes and includes['users']:
        username = includes['users'][0].get('username')
    url = f"https://twitter.com/{username}/status/{tweet_id}" if username else f"https://twitter.com/i/status/{tweet_id}"
    
    # Extract metrics
    metrics = tweet_data.get('public_metrics', {})
    retweets = metrics.get('retweet_count', 0)
    likes = metrics.get('like_count', 0)
    replies = metrics.get('reply_count', 0)
    quotes = metrics.get('quote_count', 0)
    
    # Extract media information
    media_ids = []
    if 'attachments' in tweet_data and 'media_keys' in tweet_data['attachments']:
        media_ids = tweet_data['attachments']['media_keys']
    
    # Extract author information
    author_id = tweet_data.get('author_id')
    
    return Tweet(
        id=tweet_id,
        text=text,
        created_at=created_at,
        url=url,
        author_id=author_id,
        metrics={
            'retweets': retweets,
            'likes': likes,
            'replies': replies,
            'quotes': quotes
        },
        media_ids=media_ids
    )