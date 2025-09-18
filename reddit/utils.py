import tkinter as tk
from tkinter import filedialog
import os
from datetime import datetime
from typing import Dict, Any
from .models import RedditPost

def select_image():
    root = tk.Tk()
    root.withdraw()
    
    file_path = filedialog.askopenfilename(
        title="Select Image",
        filetypes=[
            ("Image files", "*.jpg *.jpeg *.png *.gif"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    
    return file_path if file_path else None

def format_reddit_response(submission) -> RedditPost:
    try:
        submission.comments.replace_more(limit=0)
        comments = [{"author": comment.author.name if comment.author else "[deleted]",
                    "body": comment.body,
                    "score": comment.score,
                    "created_utc": datetime.fromtimestamp(comment.created_utc).strftime('%Y-%m-%d %H:%M:%S')}
                   for comment in submission.comments.list()[:10]]
    except Exception:
        comments = []
    
    return RedditPost(
        id=submission.id,
        title=submission.title,
        content=submission.selftext,
        author=submission.author.name if submission.author else "[deleted]",
        subreddit=submission.subreddit.display_name,
        created_utc=datetime.fromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
        url=submission.url,
        permalink=f"https://www.reddit.com{submission.permalink}",
        score=submission.score,
        num_comments=submission.num_comments,
        comments=comments,
        upvote_ratio=submission.upvote_ratio
    )