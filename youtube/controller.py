import os
import requests
from datetime import datetime
from .auth import YouTubeAuth
import mimetypes
import tempfile
import json

class YouTubeManager(YouTubeAuth):
    def __init__(self, user_id=None):
        super().__init__(user_id=user_id)
        if not self.access_token:
            print("No access token found. Please authenticate first.")

    def validate_credentials(self):
        return super().validate_credentials()
    
    def get_user_info(self):
        """Get current user information for exclusivity checks"""
        if not self.access_token:
            print("Error: No access token available. Cannot get user info.")
            return None
        
        # First try to get channel info using the channels API
        try:
            url = f"{self.api_base_url}/channels"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {
                "part": "snippet,id",
                "mine": "true"
            }
            
            print(f"🔍 Making API request to: {url}")
            print(f"🔍 Headers: {headers}")
            print(f"🔍 Params: {params}")
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            print(f"🔍 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"🔍 Response data: {data}")
                
                if data.get('items') and len(data['items']) > 0:
                    channel = data['items'][0]
                    user_info = {
                        'id': channel['id'],
                        'username': channel['snippet']['title'],
                        'name': channel['snippet']['title']
                    }
                    print(f"✅ Successfully got user info: {user_info}")
                    return user_info
                else:
                    print("❌ No channel data found in response")
                    return None
            elif response.status_code == 403:
                print(f"❌ 403 Forbidden - API access denied. Response: {response.text}")
                # Try alternative approach using OAuth2 userinfo endpoint
                return self._get_user_info_fallback()
            else:
                print(f"❌ API request failed with status {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting YouTube user info: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None
    
    def _get_user_info_fallback(self):
        """Fallback method to get user info using OAuth2 userinfo endpoint"""
        try:
            # Use Google's OAuth2 userinfo endpoint as fallback
            url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            print(f"🔄 Trying fallback userinfo endpoint: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            print(f"🔄 Fallback response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"🔄 Fallback response data: {data}")
                
                # Create user info from OAuth2 userinfo
                user_info = {
                    'id': data.get('id', 'unknown'),
                    'username': data.get('name', data.get('email', 'Unknown User')),
                    'name': data.get('name', data.get('email', 'Unknown User'))
                }
                print(f"✅ Successfully got user info via fallback: {user_info}")
                return user_info
            else:
                print(f"❌ Fallback also failed with status {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Fallback method failed: {e}")
            return None

    def upload_short(self, video_path, title="", description="", privacy_status="public", link=None, scheduled_time=None):
        """Upload a YouTube Short"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot upload Short.")
            return None
        
        # Prepare video metadata
        snippet = {
            "title": title or "YouTube Short",
            "description": description or "",
            "tags": ["shorts", "short"],
            "categoryId": "22"  # People & Blogs category
        }
        
        # Add link to description if provided
        if link:
            snippet["description"] += f"\n\nLink: {link}"
        
        status = {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
        
        # Scheduled publishing support
        if scheduled_time:
            try:
                from datetime import datetime, timezone
                # Accept either ISO string or timestamp; convert to RFC3339 UTC
                if isinstance(scheduled_time, str):
                    # Try both with and without seconds
                    try:
                        dt = datetime.strptime(scheduled_time, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        try:
                            dt = datetime.strptime(scheduled_time, '%Y-%m-%dT%H:%M:%S')
                        except Exception as e2:
                            print(f'Error parsing scheduled_time string: {e2}')
                            dt = None
                    if dt:
                        dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.utcfromtimestamp(float(scheduled_time)).replace(tzinfo=timezone.utc)
                # Only set publishAt if scheduled for the future
                now = datetime.utcnow().replace(tzinfo=timezone.utc)
                if dt and dt > now:
                    # YouTube requires RFC3339 UTC (e.g. 2025-08-13T19:00:00Z)
                    status["publishAt"] = dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
                    # Force privacyStatus to 'private' for scheduled publishing
                    status["privacyStatus"] = "private"
                    print(f'[YouTube Scheduling] Will schedule publish at: {status["publishAt"]} (privacyStatus forced to private)')
                else:
                    print(f'[YouTube Scheduling] Ignoring scheduled_time (not in the future or invalid): {scheduled_time}')
            except Exception as e:
                print(f'Error parsing scheduled_time for YouTube Shorts: {e}')
        
        metadata = {
            "snippet": snippet,
            "status": status
        }
        print('[YouTube Upload] Metadata payload:', metadata)
        
        # Upload video
        url = "https://www.googleapis.com/upload/youtube/v3/videos"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            # First, initiate the upload
            params = {
                "part": "snippet,status",
                "uploadType": "resumable"
            }
            
            init_response = requests.post(
                url,
                headers=headers,
                params=params,
                json=metadata
            )
            if not init_response.ok:
                print('[YouTube Upload] API error response:', init_response.text)
            init_response.raise_for_status()
            
            # Get upload URL from Location header
            upload_url = init_response.headers.get('Location')
            if not upload_url:
                print("Error: No upload URL received")
                return None
            
            # Upload the video file
            with open(video_path, 'rb') as video_file:
                video_data = video_file.read()
            
            upload_headers = {
                "Content-Type": "video/*",
                "Content-Length": str(len(video_data))
            }
            
            upload_response = requests.put(
                upload_url,
                headers=upload_headers,
                data=video_data
            )
            if not upload_response.ok:
                print('[YouTube Upload] Video upload error response:', upload_response.text)
            upload_response.raise_for_status()
            
            video_data = upload_response.json()
            
            return {
                'id': video_data.get('id'),
                'title': video_data.get('snippet', {}).get('title'),
                'description': video_data.get('snippet', {}).get('description'),
                'url': f"https://www.youtube.com/watch?v={video_data.get('id')}",
                'thumbnail_url': video_data.get('snippet', {}).get('thumbnails', {}).get('default', {}).get('url'),
                'privacy_status': video_data.get('status', {}).get('privacyStatus'),
                'created_at': video_data.get('snippet', {}).get('publishedAt'),
                'link': link
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Error uploading Short: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None
        except Exception as e:
            print(f"Unexpected error uploading Short: {e}")
            return None

    def get_channel_videos(self, max_results=50):
        """Get videos from the authenticated user's channel using uploads playlist"""
        if not self.access_token:
            print("Error: No access token available. Cannot get videos.")
            return []
        
        try:
            print(f"🔍 Getting channel videos for authenticated user...")
            
            # First, get the channel's uploads playlist ID
            channel_response = requests.get(
                f"{self.api_base_url}/channels",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"part": "contentDetails", "mine": "true"},
                timeout=10
            )
            
            print(f"🔍 Channel response status: {channel_response.status_code}")
            
            if channel_response.status_code == 403:
                print("❌ 403 Forbidden - Channel access denied. Trying alternative approach...")
                return self._get_videos_fallback(max_results)
            
            channel_response.raise_for_status()
            channel_data = channel_response.json()
            
            print(f"🔍 Channel data: {channel_data}")
            
            if not channel_data.get('items'):
                print("❌ No channel found for authenticated user")
                return []
            
            # Get the uploads playlist ID
            uploads_playlist_id = channel_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            print(f"🔍 Uploads playlist ID: {uploads_playlist_id}")
            
            # Get videos from the uploads playlist
            playlist_response = requests.get(
                f"{self.api_base_url}/playlistItems",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={
                    "part": "snippet,contentDetails",
                    "playlistId": uploads_playlist_id,
                    "maxResults": max_results,
                    "order": "date"
                },
                timeout=10
            )
            
            print(f"🔍 Playlist response status: {playlist_response.status_code}")
            
            if playlist_response.status_code == 403:
                print("❌ 403 Forbidden - Playlist access denied. Trying alternative approach...")
                return self._get_videos_fallback(max_results)
            
            playlist_response.raise_for_status()
            playlist_data = playlist_response.json()
            
            print(f"🔍 Found {len(playlist_data.get('items', []))} videos in playlist")
            
            videos = []
            for item in playlist_data.get('items', []):
                video_id = item['contentDetails']['videoId']
                snippet = item['snippet']
                
                print(f"🔍 Processing video: {video_id} - {snippet.get('title', 'No title')}")
                
                # Get additional video details
                video_response = requests.get(
                    f"{self.api_base_url}/videos",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params={
                        "part": "statistics,status,contentDetails",
                        "id": video_id
                    },
                    timeout=10
                )
                
                video_details = {}
                if video_response.status_code == 200:
                    video_data = video_response.json()
                    if video_data.get('items'):
                        video_details = video_data['items'][0]
                
                # Check if it's a Short (duration < 60 seconds)
                duration = video_details.get('contentDetails', {}).get('duration', '')
                is_short = self._is_short_duration(duration)
                
                video_info = {
                    'id': video_id,
                    'title': snippet.get('title', ''),
                    'description': snippet.get('description', ''),
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail_url': snippet.get('thumbnails', {}).get('default', {}).get('url'),
                    'created_at': snippet.get('publishedAt'),
                    'privacy_status': video_details.get('status', {}).get('privacyStatus', 'unknown'),
                    'view_count': int(video_details.get('statistics', {}).get('viewCount', 0)),
                    'like_count': int(video_details.get('statistics', {}).get('likeCount', 0)),
                    'comment_count': int(video_details.get('statistics', {}).get('commentCount', 0)),
                    'is_short': is_short,
                    'duration': duration
                }
                
                videos.append(video_info)
            
            print(f"✅ Successfully processed {len(videos)} videos")
            
            # Filter to only return Shorts
            shorts = [video for video in videos if video['is_short']]
            print(f"✅ Found {len(shorts)} YouTube Shorts")
            return shorts
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting channel videos: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return []
    
    def _get_videos_fallback(self, max_results=50):
        """Fallback method when main API calls fail - returns empty list with message"""
        print("🔄 Using fallback method for getting videos...")
        print("❌ Unable to access YouTube channel data with current permissions")
        print("💡 This might be due to:")
        print("   - Channel not being set up properly")
        print("   - Insufficient API permissions")
        print("   - YouTube API restrictions")
        print("📝 You can still upload new videos, but recent videos won't be displayed")
        return []

    def _is_short_duration(self, duration):
        """Check if video duration indicates it's a Short (< 60 seconds)"""
        if not duration:
            return False
        
        try:
            # Parse ISO 8601 duration format (PT1M30S = 1 minute 30 seconds)
            import re
            pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
            match = re.match(pattern, duration)
            
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = int(match.group(3) or 0)
                
                total_seconds = hours * 3600 + minutes * 60 + seconds
                return total_seconds <= 60
            
            return False
        except Exception:
            return False

    def get_short(self, video_id):
        """Get details for a specific Short"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot get Short details.")
            return None
        
        url = f"{self.api_base_url}/videos"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {
            "part": "snippet,statistics,status,contentDetails",
            "id": video_id
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('items'):
                video = data['items'][0]
                snippet = video['snippet']
                statistics = video.get('statistics', {})
                status = video.get('status', {})
                content_details = video.get('contentDetails', {})
                
                return {
                    'id': video['id'],
                    'title': snippet.get('title', ''),
                    'description': snippet.get('description', ''),
                    'url': f"https://www.youtube.com/watch?v={video['id']}",
                    'thumbnail_url': snippet.get('thumbnails', {}).get('default', {}).get('url'),
                    'created_at': snippet.get('publishedAt'),
                    'privacy_status': status.get('privacyStatus'),
                    'view_count': statistics.get('viewCount', 0),
                    'like_count': statistics.get('likeCount', 0),
                    'comment_count': statistics.get('commentCount', 0),
                    'duration': content_details.get('duration')
                }
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error getting Short: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def delete_short(self, video_id):
        """Delete a Short"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot delete Short.")
            return False
        
        url = f"{self.api_base_url}/videos"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"id": video_id}
        
        try:
            response = requests.delete(url, headers=headers, params=params)
            response.raise_for_status()
            
            # YouTube delete API returns empty response on success (204 No Content)
            if response.status_code in [200, 204]:
                return True
            
            return False
            
        except requests.exceptions.RequestException as e:
            print(f"Error deleting Short: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response status: {e.response.status_code}")
                print(f"Response content: {e.response.text}")
            return False

    def get_channel_analytics(self):
        """Get basic channel analytics"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot get analytics.")
            return None
        
        try:
            # Get channel statistics
            response = requests.get(
                f"{self.api_base_url}/channels",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={
                    "part": "statistics,snippet",
                    "mine": "true"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('items'):
                channel = data['items'][0]
                statistics = channel.get('statistics', {})
                snippet = channel.get('snippet', {})
                
                return {
                    'channel_name': snippet.get('title'),
                    'subscriber_count': statistics.get('subscriberCount', 0),
                    'total_views': statistics.get('viewCount', 0),
                    'video_count': statistics.get('videoCount', 0),
                    'created_at': snippet.get('publishedAt')
                }
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error getting channel analytics: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def revoke_token(self):
        """Revoke the current access token and clear stored tokens"""
        return super().revoke_token()
