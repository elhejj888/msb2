import os
import requests
from datetime import datetime
from .auth import PinterestAuth
import mimetypes
from PIL import Image
from io import BytesIO
import base64


class PinterestManager(PinterestAuth):
    def __init__(self, user_id=None):
        # Initialize with per-user token storage
        super().__init__(user_id=user_id)
        # Do NOT auto-trigger OAuth flow here; let routes call validate_credentials/connect explicitly

    def validate_credentials(self):
        return super().validate_credentials()
    
    def get_user_info(self):
        """Get current user information for exclusivity checks"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot get user info.")
            return None
        
        url = f"{self.api_base_url}/user_account"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            user_data = response.json()
            return {
                'id': user_data.get('id'),
                'username': user_data.get('username'),
                'name': user_data.get('username')  # Pinterest uses username
            }
        except requests.exceptions.RequestException as e:
            print(f"Error getting Pinterest user info: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def list_boards(self):
        """List all boards for the authenticated user"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot list boards.")
            return None
        
        url = f"{self.api_base_url}/boards"
        params = {
            "fields": "id,name,description,privacy,pin_count,url"
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except requests.exceptions.RequestException as e:
            print(f"Error listing boards: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def create_board(self, name, description=None, privacy="PUBLIC"):
        """Create a new board"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot create board.")
            return None
        
        url = f"{self.api_base_url}/boards"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "name": name,
            "privacy": privacy.upper()
        }
        if description:
            payload["description"] = description
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            board_data = response.json()
            
            # Get full board details
            board_id = board_data.get("id")
            if board_id:
                return self.get_board(board_id)
            return board_data
        except requests.exceptions.RequestException as e:
            print(f"Error creating board: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def get_board(self, board_id):
        """Get details for a specific board"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot get board details.")
            return None
        
        url = f"{self.api_base_url}/boards/{board_id}"
        params = {
            "fields": "id,name,description,privacy,pin_count,url"
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting board: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def create_pin_with_image_url(self, board_id, image_url, title="", description="", link=None):
        """Create pin using an image URL instead of uploading"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot create pin.")
            return None

        url = f"{self.api_base_url}/pins"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "board_id": board_id,
            "media_source": {
                "source_type": "image_url",
                "url": image_url
            }
        }
        if title:
            payload["title"] = title
        if description:
            payload["description"] = description
        if link:
            payload["link"] = link

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating pin: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def create_pin(self, board_id, image_path, title="", description="", link=None):
        """Robust pin creation with multiple fallbacks"""
        if not all([board_id, image_path]):
            print("Error: Missing required parameters")
            return None

        # Try direct upload first (simplified version)
        try:
            print("Attempting direct upload to Pinterest...")
            url = f"{self.api_base_url}/media"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f)}
                response = requests.post(url, headers=headers, files=files)
                
                if response.status_code == 201:
                    media_id = response.json().get('media_id')
                    print("Direct upload successful!")
                    payload = {
                        "board_id": board_id,
                        "media_source": {
                            "source_type": "image_upload",
                            "media_id": media_id
                        },
                        "title": title,
                        "description": description
                    }
                    if link: payload["link"] = link
                    return self._make_pin_request(payload)
        except Exception as e:
            print(f"Direct upload attempt failed: {str(e)}")

        # If direct upload fails, try local file upload alternative
        print("Trying alternative upload method...")
        try:
            # Convert image to base64
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            payload = {
                "board_id": board_id,
                "media_source": {
                    "source_type": "image_base64",
                    "content_type": "image/jpeg",
                    "data": encoded_string
                },
                "title": title,
                "description": description
            }
            if link: payload["link"] = link
            
            return self._make_pin_request(payload)
            
        except Exception as e:
            print(f"Alternative upload failed: {str(e)}")
            return None

    def _make_pin_request(self, payload):
        """Helper method to make pin creation request"""
        url = f"{self.api_base_url}/pins"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            print(f"Creating pin with payload: {payload}")
            response = requests.post(url, headers=headers, json=payload)
            print(f"Response: {response.status_code} - {response.text}")
            
            if response.status_code == 201:
                return response.json()
            return None
        except Exception as e:
            print(f"Pin creation failed: {str(e)}")
            return None

    def upload_to_temp_host(self, image_path):
        """Upload image to a temporary hosting service (for testing)"""
        try:
            # This is just an example - you'd need to implement actual upload logic
            # to a service like Imgur or your own server
            print("Uploading image to temporary host...")
            # Implement actual upload logic here
            return "https://example.com/your-image.jpg"  # Return the hosted URL
        except Exception as e:
            print(f"Error uploading to temp host: {e}")
            return None
    
    def upload_image(self, image_path):
        """Improved Pinterest image upload with better error handling"""
        if not os.path.exists(image_path):
            print(f"Error: Image file not found at {image_path}")
            return None

        try:
            # Verify image file
            with Image.open(image_path) as img:
                img.verify()  # Verify it's a valid image file
            
            # Prepare the upload
            url = f"{self.api_base_url}/media"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
            }
            
            mime_type = mimetypes.guess_type(image_path)[0] or 'image/jpeg'
            filename = os.path.basename(image_path)

            with open(image_path, 'rb') as f:
                files = {'file': (filename, f, mime_type)}
                
                # Add timeout and retry logic
                for attempt in range(3):
                    try:
                        response = requests.post(
                            url,
                            headers=headers,
                            files=files,
                            timeout=30
                        )
                        
                        if response.status_code == 201:
                            return response.json().get('media_id')
                        else:
                            print(f"Upload attempt {attempt + 1} failed: {response.status_code}")
                            print(response.text)
                    except (requests.exceptions.RequestException, ConnectionError) as e:
                        print(f"Upload attempt {attempt + 1} error: {str(e)}")
                    
                    if attempt < 2:
                        time.sleep(2)  # Wait before retrying

            return None

        except Exception as e:
            print(f"Image processing error: {str(e)}")
            return None

    def upload_to_imgur(self, image_path):
        """More reliable Imgur upload with proper error handling"""
        IMGUR_CLIENT_ID = "YOUR_IMGUR_CLIENT_ID"  # Replace with your actual client ID
        
        try:
            # Verify and prepare image
            with Image.open(image_path) as img:
                # Convert to RGB if needed and resize if too large
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                if max(img.size) > 2000:
                    img.thumbnail((2000, 2000))
                
                # Save to buffer
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                buffer.seek(0)
                image_data = buffer.read()

            # Encode and prepare request
            b64_image = base64.b64encode(image_data).decode('utf-8')
            headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
            data = {
                'image': b64_image,
                'type': 'base64',
                'title': 'Pinterest Upload'
            }

            # Add retry logic
            for attempt in range(3):
                try:
                    response = requests.post(
                        "https://api.imgur.com/3/image",
                        headers=headers,
                        data=data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        return response.json()['data']['link']
                    else:
                        print(f"Imgur attempt {attempt + 1} failed: {response.status_code}")
                        print(response.text)
                except (requests.exceptions.RequestException, ConnectionError) as e:
                    print(f"Imgur attempt {attempt + 1} error: {str(e)}")
                
                if attempt < 2:
                    time.sleep(2)  # Wait before retrying

            return None

        except Exception as e:
            print(f"Imgur processing error: {str(e)}")
            return None



    # Alternative method using the Pinterest API v5 recommended approach
    def upload_image_with_proper_headers(self, image_path):
        """Upload image with explicit multipart boundary handling"""
        if not os.path.exists(image_path):
            print(f"Error: Image file not found at {image_path}")
            return None
        
        print(f"Attempting to upload image: {image_path}")
        
        url = f"{self.api_base_url}/media"
        
        try:
            # Get the mime type and filename
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                mime_type = 'image/jpeg'
            
            filename = os.path.basename(image_path)
            
            # Use requests Session for better handling
            session = requests.Session()
            session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
            
            with open(image_path, 'rb') as f:
                files = {
                    'file': (filename, f, mime_type)
                }
                
                print("Sending upload request with session...")
                response = session.post(url, files=files)
                
                print(f"Response status: {response.status_code}")
                print(f"Response content: {response.text}")
                
                if response.status_code == 201:
                    media_data = response.json()
                    media_id = media_data.get('media_id')
                    print(f"Upload successful! Media ID: {media_id}")
                    return media_id
                else:
                    print(f"Upload failed with status: {response.status_code}")
                    return None
                    
        except Exception as e:
            print(f"Error uploading image: {e}")
            return None


    # Method using form data with explicit boundary
    def upload_image_form_data(self, image_path):
        """Upload image using explicit form data construction"""
        if not os.path.exists(image_path):
            print(f"Error: Image file not found at {image_path}")
            return None
        
        print(f"Attempting to upload image: {image_path}")
        
        url = f"{self.api_base_url}/media"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        
        try:
            from requests_toolbelt.multipart.encoder import MultipartEncoder
            
            # Get the mime type and filename
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                mime_type = 'image/jpeg'
            
            filename = os.path.basename(image_path)
            
            # Create multipart encoder
            with open(image_path, 'rb') as f:
                multipart_data = MultipartEncoder(
                    fields={
                        'file': (filename, f, mime_type)
                    }
                )
                
                headers['Content-Type'] = multipart_data.content_type
                
                print("Sending upload request with multipart encoder...")
                response = requests.post(url, headers=headers, data=multipart_data)
                
                print(f"Response status: {response.status_code}")
                print(f"Response content: {response.text}")
                
                if response.status_code == 201:
                    media_data = response.json()
                    media_id = media_data.get('media_id')
                    print(f"Upload successful! Media ID: {media_id}")
                    return media_id
                else:
                    print(f"Upload failed with status: {response.status_code}")
                    return None
                    
        except ImportError:
            print("requests_toolbelt not available, falling back to standard method")
            return self.upload_image_with_proper_headers(image_path)
        except Exception as e:
            print(f"Error uploading image: {e}")
            return None

    # Alternative method using Pinterest's recommended approach for media upload
    def upload_image_v2(self, image_path):
        """Alternative upload method with explicit multipart construction"""
        if not os.path.exists(image_path):
            print(f"Error: Image file not found at {image_path}")
            return None
        
        print(f"Attempting to upload image: {image_path}")
        
        url = f"{self.api_base_url}/media"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        
        try:
            # Use requests-toolbelt for better multipart handling if needed
            # For now, let's try the standard approach with proper data structure
            
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                mime_type = 'image/jpeg'
            
            filename = os.path.basename(image_path)
            
            with open(image_path, 'rb') as image_file:
                # Create the multipart form data
                files = {
                    'file': (filename, image_file.read(), mime_type)
                }
                
                print("Sending upload request...")
                response = requests.post(url, headers=headers, files=files)
                
                print(f"Response status: {response.status_code}")
                print(f"Response content: {response.text}")
                
                if response.status_code == 201:
                    media_data = response.json()
                    media_id = media_data.get('media_id')
                    print(f"Upload successful! Media ID: {media_id}")
                    return media_id
                else:
                    print(f"Upload failed with status: {response.status_code}")
                    return None
                    
        except Exception as e:
            print(f"Error uploading image: {e}")
            return None

    # Method to register media upload (Pinterest API v5 two-step process)
    def register_and_upload_media(self, image_path):
        """Two-step media upload process for Pinterest API v5"""
        if not os.path.exists(image_path):
            print(f"Error: Image file not found at {image_path}")
            return None
        
        # Step 1: Register the media upload
        register_url = f"{self.api_base_url}/media"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Get file info
        file_size = os.path.getsize(image_path)
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'
        
        # Register payload
        register_payload = {
            "media_type": "image"
        }
        
        try:
            print("Step 1: Registering media upload...")
            register_response = requests.post(register_url, headers=headers, json=register_payload)
            print(f"Register response status: {register_response.status_code}")
            print(f"Register response: {register_response.text}")
            
            if register_response.status_code != 201:
                print("Failed to register media upload")
                return None
            
            register_data = register_response.json()
            media_id = register_data.get('media_id')
            upload_url = register_data.get('upload_url')
            upload_parameters = register_data.get('upload_parameters', {})
            
            if not upload_url:
                print("No upload URL received from registration")
                return None
            
            print(f"Step 2: Uploading to {upload_url}")
            
            # Step 2: Upload the file
            with open(image_path, 'rb') as f:
                # Prepare upload data
                files = {'file': (os.path.basename(image_path), f, mime_type)}
                data = upload_parameters  # Include any required parameters
                
                upload_response = requests.post(upload_url, files=files, data=data)
                print(f"Upload response status: {upload_response.status_code}")
                print(f"Upload response: {upload_response.text}")
                
                if upload_response.status_code in [200, 201, 204]:
                    print(f"Upload successful! Media ID: {media_id}")
                    return media_id
                else:
                    print("Upload failed")
                    return None
                    
        except Exception as e:
            print(f"Error in media upload process: {e}")
            return None

# Alternative create_pin method that uses image URL instead of upload
    def create_pin_with_url(self, board_id, image_url, title="", description="", link=None):
        """Create a new pin using an image URL instead of upload"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot create pin.")
            return None
        
        url = f"{self.api_base_url}/pins"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "board_id": board_id,
            "media_source": {
                "source_type": "image_url",
                "url": image_url
            }
        }
        if title:
            payload["title"] = title
        if description:
            payload["description"] = description
        if link:
            payload["link"] = link
        
        try:
            print(f"Creating pin with payload: {payload}")
            response = requests.post(url, headers=headers, json=payload)
            print(f"Pin creation response status: {response.status_code}")
            print(f"Pin creation response: {response.text}")
            
            if response.status_code == 201:
                pin_data = response.json()
                pin_id = pin_data.get("id")
                if pin_id:
                    return self.get_pin(pin_id)
                return pin_data
            else:
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            print(f"Error creating pin: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def get_all_pins(self, limit=None):
        """Get all pins across all boards"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot get pin details.")
            return None
        
        pins = []
        boards = self.list_boards()
        
        if not boards:
            print("No boards found.")
            return None
        
        for board in boards:
            if not board or 'id' not in board:
                continue
                
            url = f"{self.api_base_url}/boards/{board['id']}/pins"
            params = {
                "fields": "id,title,description,link,url,board_id,created_at,media",
                "page_size": 100  # Maximum allowed by Pinterest API
            }
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            try:
                while url:
                    response = requests.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'items' in data:
                        pins.extend(data['items'])
                    
                    # Handle pagination
                    if 'next' in data.get('page', {}).get('cursor', ''):
                        params['cursor'] = data['page']['cursor']
                    else:
                        url = None
                        
            except requests.exceptions.RequestException as e:
                print(f"Error getting pins for board {board['id']}: {e}")
                if hasattr(e, 'response') and e.response:
                    print(f"Response content: {e.response.text}")
                continue
        
        # Sort pins by created_at in descending order (newest first)
        pins.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Apply limit if specified
        if limit is not None:
            pins = pins[:limit]
            
        return pins if pins else None

    def get_pin(self, pin_id=None):
        """
        Get details for a specific pin or all pins if no pin_id is provided
        If pin_id is provided, returns single pin details
        If pin_id is None, returns all pins across all boards
        """
        if pin_id:
            # Original single pin implementation
            if not self.validate_credentials():
                print("Error: Invalid credentials. Cannot get pin details.")
                return None
            
            url = f"{self.api_base_url}/pins/{pin_id}"
            params = {
                "fields": "id,title,description,link,url,board_id,created_at,media"
            }
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error getting pin: {e}")
                if hasattr(e, 'response') and e.response:
                    print(f"Response content: {e.response.text}")
                return None
        else:
            # Return all pins
            return self.get_all_pins()

    def delete_pin(self, pin_id):
        """Delete a pin"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot delete pin.")
            return False
        
        url = f"{self.api_base_url}/pins/{pin_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.delete(url, headers=headers)
            response.raise_for_status()
            
            # Pinterest delete API returns empty response on success (204 No Content)
            # Check if response is successful (2xx status code)
            if response.status_code in [200, 204]:
                return True
        
            # Try to parse JSON response if available
            try:
                if response.text.strip():
                    return response.json().get("success", False)
                else:
                    # Empty response with 2xx status means success
                    return True
            except ValueError:
                # Not JSON, but 2xx status means success
                return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error deleting pin: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response status: {e.response.status_code}")
                print(f"Response content: {e.response.text}")
            return False
    
    def revoke_token(self):
        """Revoke the current access token and clear stored tokens"""
        if self.access_token:
            try:
                # Pinterest doesn't have a token revocation endpoint, so we just clear locally
                pass
            except Exception as e:
                print(f"Warning: Could not revoke token with API: {e}")
        
        # Clear stored tokens
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # Remove token file
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                print(f"✅ Token file {self.token_file} removed")
        except Exception as e:
            print(f"Warning: Could not remove token file: {e}")
        
        return True