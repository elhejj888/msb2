from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class RedditPost:
    id: str
    title: str
    content: str
    author: str
    subreddit: str
    created_utc: str
    url: str
    permalink: str
    score: int
    num_comments: int
    comments: Optional[List[Dict]] = None
    upvote_ratio: Optional[float] = None