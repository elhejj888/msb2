import tkinter as tk
from tkinter import filedialog
import os
import mimetypes

def select_video():
    """Open file dialog to select a video file"""
    root = tk.Tk()
    root.withdraw()
    
    file_path = filedialog.askopenfilename(
        title="Select Video",
        filetypes=[
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
            ("MP4 files", "*.mp4"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    return file_path if file_path else None

def validate_video_file(file_path):
    """Validate if the file is a valid video file"""
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    # Check file size (max 15GB for YouTube)
    file_size = os.path.getsize(file_path)
    max_size = 15 * 1024 * 1024 * 1024  # 15GB in bytes
    
    if file_size > max_size:
        return False, "File size exceeds 15GB limit"
    
    # Check file extension
    valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext not in valid_extensions:
        return False, f"Invalid file format. Supported formats: {', '.join(valid_extensions)}"
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and not mime_type.startswith('video/'):
        return False, "File is not a valid video format"
    
    return True, "Valid video file"

def format_duration(duration_str):
    """Convert ISO 8601 duration to human readable format"""
    if not duration_str:
        return "Unknown"
    
    try:
        import re
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            
            parts = []
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if seconds > 0:
                parts.append(f"{seconds}s")
            
            return " ".join(parts) if parts else "0s"
        
        return duration_str
    except Exception:
        return duration_str

def format_number(number):
    """Format large numbers with K, M, B suffixes"""
    try:
        num = int(number)
        if num >= 1000000000:
            return f"{num/1000000000:.1f}B"
        elif num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}K"
        else:
            return str(num)
    except (ValueError, TypeError):
        return str(number)

def is_short_video(duration_str):
    """Check if video duration indicates it's a YouTube Short (≤ 60 seconds)"""
    if not duration_str:
        return False
    
    try:
        import re
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            
            total_seconds = hours * 3600 + minutes * 60 + seconds
            return total_seconds <= 60
        
        return False
    except Exception:
        return False

def validate_short_requirements(file_path):
    """Validate if video meets YouTube Shorts requirements"""
    errors = []
    
    # Basic file validation
    is_valid, message = validate_video_file(file_path)
    if not is_valid:
        errors.append(message)
        return False, errors
    
    # Check file size for Shorts (recommended max 256MB)
    file_size = os.path.getsize(file_path)
    max_short_size = 256 * 1024 * 1024  # 256MB in bytes
    
    if file_size > max_short_size:
        errors.append("File size exceeds recommended 256MB limit for Shorts")
    
    # Note: We can't easily check video duration, aspect ratio, or resolution 
    # without additional video processing libraries like ffmpeg-python
    # These would need to be checked on the client side or with additional dependencies
    
    return len(errors) == 0, errors
