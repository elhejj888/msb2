import os
import mimetypes
from datetime import datetime

def validate_video_file(file_path):
    """Validate if the file is a supported video format"""
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    # Check file size (TikTok has limits)
    file_size = os.path.getsize(file_path)
    max_size = 287 * 1024 * 1024  # 287MB limit for TikTok
    
    if file_size > max_size:
        return False, f"File size ({file_size / (1024*1024):.1f}MB) exceeds TikTok limit (287MB)"
    
    # Check file type
    mime_type, _ = mimetypes.guess_type(file_path)
    supported_types = ['video/mp4', 'video/quicktime', 'video/x-msvideo']
    
    if mime_type not in supported_types:
        return False, f"Unsupported file type: {mime_type}"
    
    return True, "Valid video file"

def format_tiktok_description(description, hashtags=None):
    """Format description with hashtags for TikTok"""
    formatted_desc = description.strip()
    
    if hashtags:
        if isinstance(hashtags, str):
            hashtags = [tag.strip() for tag in hashtags.split(',')]
        
        # Ensure hashtags start with #
        formatted_hashtags = []
        for tag in hashtags:
            if tag.strip():
                if not tag.startswith('#'):
                    tag = '#' + tag
                formatted_hashtags.append(tag)
        
        if formatted_hashtags:
            formatted_desc += '\n\n' + ' '.join(formatted_hashtags)
    
    return formatted_desc

def parse_scheduled_time(time_str):
    """Parse scheduled time string to datetime object"""
    try:
        # Support multiple formats
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M',
            '%m/%d/%Y %H:%M',
            '%d/%m/%Y %H:%M'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        
        raise ValueError("Invalid time format")
    except Exception as e:
        return None

def get_video_duration_estimate(file_path):
    """Get estimated video duration (placeholder - would need video processing library)"""
    # This would typically use ffmpeg or similar to get actual duration
    # For now, return a placeholder based on file size
    try:
        file_size = os.path.getsize(file_path)
        # Rough estimate: 1MB per 10 seconds for typical TikTok quality
        estimated_duration = file_size / (1024 * 1024) * 10
        return min(estimated_duration, 180)  # TikTok max is 3 minutes
    except:
        return 60  # Default estimate
