import tkinter as tk
from tkinter import filedialog
import os
from datetime import datetime
from typing import Dict, Any
from .models import TikTokVideo

def select_video():
    root = tk.Tk()
    root.withdraw()
    
    file_path = filedialog.askopenfilename(
        title="Select Video",
        filetypes=[
            ("Video files", "*.mp4 *.mov *.avi *.mkv"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    
    return file_path if file_path else None

def format_tiktok_response(video_data: Dict) -> TikTokVideo:
    return TikTokVideo(
        id=video_data.get('id'),
        caption=video_data.get('desc', ''),
        author=video_data.get('author', {}).get('uniqueId', ''),
        likes=video_data.get('stats', {}).get('diggCount', 0),
        comments=video_data.get('stats', {}).get('commentCount', 0),
        shares=video_data.get('stats', {}).get('shareCount', 0),
        views=video_data.get('stats', {}).get('playCount', 0),
        created_time=datetime.fromtimestamp(video_data.get('createTime', 0)).isoformat(),
        url=f"https://www.tiktok.com/@{video_data.get('author', {}).get('uniqueId', '')}/video/{video_data.get('id', '')}",
        hashtags=[tag.get('name') for tag in video_data.get('challenges', [])],
        music=video_data.get('music', {}).get('title')
    )