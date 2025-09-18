from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class InstagramPost:
    id: str
    caption: str
    media_type: str
    created_time: str
    permalink: str
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    likes: int = 0
    comments: int = 0
    username: Optional[str] = None