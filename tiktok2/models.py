from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime

@dataclass
class TikTokVideo:
    id: str
    caption: str
    author: str
    likes: int
    comments: int
    shares: int
    views: int
    created_time: str
    url: str
    hashtags: List[str]
    music: Optional[str] = None