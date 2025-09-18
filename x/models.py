from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class Tweet:
    id: str
    text: str
    created_at: str
    url: str
    author_id: Optional[str] = None
    metrics: Optional[Dict] = None
    media_ids: Optional[List[str]] = None
    in_reply_to: Optional[str] = None