import os
import requests
import json
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from .auth import InstagramAuth
from .utils import convert_to_jpeg


class InstagramManager:
    def __init__(self):
        self.auth = InstagramAuth()
        self.imgbb_api_key = os.getenv('IMGBB_API_KEY')
        self.cloudinary_cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
        self.cloudinary_api_key = os.getenv('CLOUDINARY_API_KEY')
        self.cloudinary_api_secret = os.getenv('CLOUDINARY_API_SECRET')
        self.api_version = 'v18.0'

    def validate_credentials(self):
        """
        Validate the access token and permissions
        """
        if not self.auth.access_token or not self.auth.user_id:
            print("Error: Access token or user ID is not set.")
            return False
        
        try:
            # Test with a simple API call to get user info
            test_url = f'https://graph.facebook.com/{self.api_version}/{self.auth.user_id}?fields=id,username&access_token={self.auth.access_token}'
            test_response = requests.get(test_url)
            
            if test_response.status_code == 200:
                user_data = test_response.json()
                print(f"✓ Connected to Instagram account: {user_data.get('username', 'Unknown')}")
                return True
            else:
                print(f"✗ Credential validation failed: {test_response.status_code}")
                print(f"Response: {test_response.text}")
                return False
                
        except Exception as e:
            print(f"Error validating credentials: {e}")
            return False

    def _retry_with_different_hosting(self, image_path, caption=None, is_carousel_item=False):
            """
            Retry upload with different hosting service or direct base64 approach
            """
            print("Retrying with alternative hosting method...")
            
            # If we used ImgBB, try Cloudinary
            if self.imgbb_api_key and all([self.cloudinary_cloud_name, self.cloudinary_api_key, self.cloudinary_api_secret]):
                print("Trying Cloudinary instead of ImgBB...")
                image_url = self._upload_to_cloudinary(image_path)
                if image_url:
                    return self._create_media_container(image_url, caption, is_carousel_item)
            
            print("All hosting methods failed.")
            return None

    def _upload_to_imgbb(self, image_path):
        """
        Upload image to ImgBB with better URL handling for Instagram compatibility
        """
        if not self.imgbb_api_key:
            return None
            
        try:
            # Convert to JPEG if not already (Instagram only supports JPEG)
            jpeg_path = convert_to_jpeg(image_path)
            if not jpeg_path:
                return None
                
            url = "https://api.imgbb.com/1/upload"
            
            with open(jpeg_path, "rb") as file:
                files = {"image": file}
                data = {
                    "key": self.imgbb_api_key,
                    "expiration": 15552000  # 6 months expiration
                }
                
                response = requests.post(url, files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        # Use the direct URL that Instagram can access
                        image_url = result["data"]["url"]
                        
                        # Test if URL is accessible
                        if self._test_url_for_instagram(image_url):
                            print(f"✓ Image uploaded to ImgBB: {image_url}")
                            return image_url
                        else:
                            print("ImgBB URL failed Instagram accessibility test")
                            return None
                                    
                            # Clean up temporary JPEG file if created
                            if jpeg_path != image_path:
                                try:
                                    os.remove(jpeg_path)
                                except:
                                    pass
                    
        except Exception as e:
            print(f"Error uploading to ImgBB: {e}")
        
        return None

    def _upload_to_cloudinary(self, image_path):
        """
        Upload image to Cloudinary with Instagram-compatible settings
        """
        if not all([self.cloudinary_cloud_name, self.cloudinary_api_key, self.cloudinary_api_secret]):
            return None
            
        try:
            # Convert to JPEG if needed
            jpeg_path = convert_to_jpeg(image_path)
            if not jpeg_path:
                return None
                
            import hashlib
            import hmac
            import time
            
            # Prepare upload parameters for Instagram compatibility
            timestamp = int(time.time())
            params = {
                'timestamp': timestamp,
                'format': 'jpg',  # Force JPEG format
                'quality': 'auto:good',  # Good quality for Instagram
                'fetch_format': 'auto'
            }
            
            # Create signature - fix the parameter ordering
            params_to_sign = {
                'timestamp': timestamp,
                'api_key': self.cloudinary_api_key,
                'format': 'jpg',
                'quality': 'auto:good'
            }
            
            # Sort parameters and create signature string
            sorted_params = sorted(params_to_sign.items())
            params_string = '&'.join([f'{k}={v}' for k, v in sorted_params])
            
            signature = hmac.new(
                self.cloudinary_api_secret.encode('utf-8'),
                params_string.encode('utf-8'),
                hashlib.sha1
            ).hexdigest()
            
            # Upload file
            url = f"https://api.cloudinary.com/v1_1/{self.cloudinary_cloud_name}/image/upload"
            
            with open(jpeg_path, 'rb') as file:
                files = {'file': file}
                data = {
                    'api_key': self.cloudinary_api_key,
                    'timestamp': timestamp,
                    'signature': signature,
                    'format': 'jpg',
                    'quality': 'auto:good'
                }
                
                response = requests.post(url, files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    # Use secure_url which is HTTPS and directly accessible
                    image_url = result.get('secure_url')
                    if image_url:
                        print(f"✓ Image uploaded to Cloudinary: {image_url}")
                        
                        # Clean up temporary JPEG file if created
                        if jpeg_path != image_path:
                            try:
                                os.remove(jpeg_path)
                            except:
                                pass
                        
                        return image_url
                else:
                    print(f"Cloudinary upload failed: {response.status_code}")
                    print(f"Response: {response.text}")
                    
            # Clean up temporary JPEG file if created
            if jpeg_path != image_path:
                try:
                    os.remove(jpeg_path)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error uploading to Cloudinary: {e}")
        
        return None

    def _upload_image_to_hosting(self, image_path):
        """
        Upload image to available hosting service with Instagram compatibility
        """
        print(f"Uploading image: {os.path.basename(image_path)}")
        
        # Try Cloudinary first (generally more reliable for Instagram)
        if all([self.cloudinary_cloud_name, self.cloudinary_api_key, self.cloudinary_api_secret]):
            print("Trying Cloudinary first...")
            image_url = self._upload_to_cloudinary(image_path)
            if image_url:
                return image_url
        
        # Try ImgBB as fallback
        if self.imgbb_api_key:
            print("Trying ImgBB...")
            image_url = self._upload_to_imgbb(image_path)
            if image_url:
                return image_url
        
        print("Error: No working image hosting service available.")
        print("For best Instagram compatibility, use Cloudinary with these .env settings:")
        print("- CLOUDINARY_CLOUD_NAME=")
        print("- CLOUDINARY_API_KEY=")
        print("- CLOUDINARY_API_SECRET=")
        
        return None

    def _upload_media_fixed(self, image_path, caption=None, is_carousel_item=False):
        """
        Fixed media upload method - Instagram API doesn't support direct file uploads
        """
        try:
            # Validate file
            if not os.path.exists(image_path):
                print(f"Error: File not found at {image_path}")
                return None
            
            file_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
            file_ext = os.path.splitext(image_path)[1].lower()
            
            if file_ext not in ['.jpg', '.jpeg', '.png']:
                print(f"Unsupported file format: {file_ext}. Supported: .jpg, .jpeg, .png")
                return None
            
            if file_size > 8:
                print(f"File too large: {file_size:.2f}MB (max 8MB)")
                return None
            
            print(f"Processing: {os.path.basename(image_path)} ({file_size:.2f}MB)")
            
            # Upload to hosting service (Instagram requires hosted URLs)
            print("Uploading to hosting service...")
            image_url = self._upload_image_to_hosting(image_path)
            
            if not image_url:
                print("Failed to upload image to hosting service")
                return None
            
            # Create Instagram media container with hosted URL
            url = f'https://graph.facebook.com/{self.auth.api_version}/{self.auth.user_id}/media'
            
            data = {
                'access_token': self.auth.access_token,
                'image_url': image_url,
                # Remove media_type parameter as it's causing issues
            }
            
            if caption and not is_carousel_item:
                data['caption'] = caption
            
            print(f"Creating Instagram media container with hosted URL...")
            response = requests.post(url, data=data)
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                container_id = result.get('id')
                if container_id:
                    print(f"✓ Media container created. ID: {container_id}")
                    return container_id
                else:
                    print("Upload response missing container ID")
                    print(f"Response: {response.text}")
                    return None
            else:
                print(f"Upload failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error details: {json.dumps(error_data, indent=2)}")
                    
                    # Provide specific error guidance
                    error_message = error_data.get('error', {}).get('message', '')
                    if 'image_url' in error_message or 'media URI' in error_message:
                        print("Tip: The image hosting URL may not be accessible. Trying alternative hosting...")
                        # Try a different hosting approach
                        return self._retry_with_different_hosting(image_path, caption, is_carousel_item)
                    elif 'permissions' in error_message.lower():
                        print("Tip: Check if your access token has instagram_content_publish permission")
                    elif 'expired' in error_message.lower():
                        print("Tip: Your access token may have expired. Please refresh it.")
                        
                except:
                    print(f"Raw error response: {response.text}")
                return None
                    
        except Exception as e:
            print(f"Exception during upload: {e}")
            import traceback
            traceback.print_exc()
            return None

    def create_post(self, caption, image_path=None, carousel_images=None):
        """
        Create a new post on Instagram with improved error handling
        """
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot create post.")
            return None
        
        if not image_path and not carousel_images:
            print("Error: Instagram requires at least one image for posting.")
            return None
        
        try:
            # Handle single image post
            if image_path and os.path.exists(image_path):
                container_id = self._upload_media_fixed(image_path, caption)
                if not container_id:
                    return None
                return self._publish_media(container_id)
            
            # Handle carousel post
            elif carousel_images and all(os.path.exists(img) for img in carousel_images):
                container_ids = []
                for i, img_path in enumerate(carousel_images):
                    # Only add caption to the first image for carousel
                    img_caption = caption if i == 0 else ""
                    container_id = self._upload_media_fixed(img_path, img_caption, is_carousel_item=True)
                    if container_id:
                        container_ids.append(container_id)
                
                if not container_ids:
                    print("Failed to upload any images for carousel")
                    return None
                
                # Create carousel container
                carousel_container_id = self._create_carousel_container(container_ids, caption)
                if not carousel_container_id:
                    return None
                
                return self._publish_media(carousel_container_id)
            
            else:
                print("Error: Image file(s) not found.")
                return None
                
        except Exception as e:
            print(f"Error creating post: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _create_media_container(self, image_url, caption=None, is_carousel_item=False):
        """
        Create media container with better error handling
        """
        url = f'https://graph.facebook.com/{self.api_version}/{self.auth.user_id}/media'
        
        data = {
            'access_token': self.auth.access_token,
            'image_url': image_url,
        }
        
        if caption and not is_carousel_item:
            data['caption'] = caption
        
        try:
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                container_id = result.get('id')
                if container_id:
                    print(f"✓ Media container created. ID: {container_id}")
                    return container_id
            
            print(f"Failed to create media container: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
        except Exception as e:
            print(f"Error creating media container: {e}")
            return None

    def _create_carousel_container(self, container_ids, caption):
        """
        Create a carousel container with multiple media items
        """
        url = f'https://graph.facebook.com/{self.api_version}/{self.auth.user_id}/media'
        
        data = {
            'access_token': self.auth.access_token,
            'media_type': 'CAROUSEL',
            'children': ','.join(container_ids),
            'caption': caption
        }
        
        try:
            print(f"Creating carousel with {len(container_ids)} items")
            response = requests.post(url, data=data)
            
            print(f"Carousel creation response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                carousel_id = result.get('id')
                if carousel_id:
                    print(f"✓ Carousel container created. ID: {carousel_id}")
                    return carousel_id
                else:
                    print(f"Failed to get carousel ID from response: {response.text}")
            else:
                print(f"Failed to create carousel container: {response.text}")
            
            return None
            
        except Exception as e:
            print(f"Error creating carousel: {e}")
            return None

    def _publish_media(self, container_id):
        """
        Publish media using a container ID
        """
        url = f'https://graph.facebook.com/{self.api_version}/{self.auth.user_id}/media_publish'
        
        data = {
            'access_token': self.auth.access_token,
            'creation_id': container_id
        }
        
        try:
            print(f"Publishing container ID: {container_id}")
            response = requests.post(url, data=data)
            
            print(f"Publish response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                media_id = result.get('id')
                if media_id:
                    print(f"✓ Media published successfully! Media ID: {media_id}")
                    
                    # Get permalink
                    permalink_url = f'https://graph.facebook.com/{self.api_version}/{media_id}?fields=permalink&access_token={self.auth.access_token}'
                    try:
                        permalink_response = requests.get(permalink_url)
                        if permalink_response.status_code == 200:
                            permalink_data = permalink_response.json()
                            permalink = permalink_data.get('permalink')
                            if not permalink:
                                permalink = f"https://www.instagram.com/p/{media_id}"
                        else:
                            permalink = f"https://www.instagram.com/p/{media_id}"
                    except:
                        permalink = f"https://www.instagram.com/p/{media_id}"
                    
                    return {
                        'id': media_id,
                        'permalink': permalink
                    }
                else:
                    print(f"Failed to get media ID from response: {response.text}")
            else:
                print(f"Failed to publish media: {response.text}")
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', '')
                    if 'creation_id' in error_message:
                        print("Tip: The media container may not be ready yet. Try waiting a few seconds and retry.")
                    elif 'permissions' in error_message.lower():
                        print("Tip: Check if your access token has instagram_content_publish permission")
                except:
                    pass
            
            return None
            
        except Exception as e:
            print(f"Error publishing media: {e}")
            return None


    def read_post(self, post_id):
        """
        Read a post by its ID with better error handling
        """
        if not self.validate_credentials():
            return None
        
        fields = [
            'id', 'caption', 'media_type', 'media_url', 'permalink',
            'thumbnail_url', 'timestamp', 'username', 'comments_count',
            'like_count'
        ]
        
        url = f'https://graph.facebook.com/{self.api_version}/{post_id}'
        params = {
            'fields': ','.join(fields),
            'access_token': self.auth.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            post_data = response.json()
            
            return {
                'id': post_data.get('id'),
                'caption': post_data.get('caption', '[No caption]'),
                'media_type': post_data.get('media_type'),
                'created_time': post_data.get('timestamp'),
                'permalink': post_data.get('permalink'),
                'image_url': post_data.get('media_url'),
                'thumbnail_url': post_data.get('thumbnail_url'),
                'likes': post_data.get('like_count', 0),
                'comments': post_data.get('comments_count', 0),
                'username': post_data.get('username')
            }
        except Exception as e:
            print(f"Error reading post: {e}")
            return None
    
    def get_user_posts(self, limit=10):
        """
        Get recent posts from the user
        """
        if not self.validate_credentials():
            return None
        
        fields = [
            'id', 'caption', 'media_type', 'media_url', 'permalink',
            'thumbnail_url', 'timestamp', 'username', 'comments_count',
            'like_count'
        ]
        
        url = f'https://graph.facebook.com/{self.api_version}/{self.auth.user_id}/media'
        params = {
            'fields': ','.join(fields),
            'limit': limit,
            'access_token': self.auth.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for post in data.get('data', []):
                formatted_post = {
                    'id': post.get('id'),
                    'caption': post.get('caption', '[No caption]'),
                    'media_type': post.get('media_type'),
                    'created_time': post.get('timestamp'),
                    'permalink': post.get('permalink'),
                    'image_url': post.get('media_url'),
                    'thumbnail_url': post.get('thumbnail_url'),
                    'likes': post.get('like_count', 0),
                    'comments': post.get('comments_count', 0)
                }
                posts.append(formatted_post)
            
            return posts
        except Exception as e:
            print(f"Error retrieving posts: {e}")
            return None
    
    def delete_post(self, post_id):
        """
        Delete a post
        """
        if not self.validate_credentials():
            return False
        
        url = f'https://graph.facebook.com/{self.api_version}/{post_id}'
        params = {'access_token': self.auth.access_token}
        
        try:
            response = requests.delete(url, params=params)
            response.raise_for_status()
            
            result = response.json()
            if result.get('success', False):
                print("Post deleted successfully!")
                return True
            else:
                print("Failed to delete post.")
                return False
        except Exception as e:
            print(f"Error deleting post: {e}")
            return False