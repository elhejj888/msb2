"""
Connection Service for managing social media account exclusivity
"""
from models import db, SocialMediaConnection, User
from sqlalchemy.exc import IntegrityError
import json
from datetime import datetime

class ConnectionService:
    """Service for managing social media connections with account exclusivity"""
    
    # Platforms for which account-level exclusivity is enforced
    # Enforce exclusivity for Facebook, Instagram, YouTube, Pinterest, and X (Twitter)
    EXCLUSIVE_PLATFORMS = {"facebook", "instagram", "youtube", "pinterest", "x"}

    @staticmethod
    def check_account_availability(platform, platform_user_id, current_user_id=None):
        """
        Check if a social media account is available for connection
        
        Args:
            platform (str): Platform name ('x', 'reddit', 'pinterest', 'tiktok')
            platform_user_id (str): Social media account ID
            current_user_id (int, optional): Current user ID to exclude from check
            
        Returns:
            dict: {
                'available': bool,
                'connected_user_id': int or None,
                'connected_username': str or None
            }
        """
        try:
            # If platform is not exclusive, always allow connection
            if str(platform).lower() not in ConnectionService.EXCLUSIVE_PLATFORMS:
                return {
                    'available': True,
                    'connected_user_id': None,
                    'connected_username': None
                }
            # Ensure platform_user_id is not empty
            if not platform_user_id or platform_user_id.strip() == '':
                print(f"Warning: Empty platform_user_id provided for platform {platform}")
                return {
                    'available': True,  # Allow connection if no valid ID provided
                    'connected_user_id': None,
                    'connected_username': None,
                    'warning': 'Empty platform_user_id'
                }
            
            # Clean the platform_user_id (remove whitespace)
            platform_user_id = str(platform_user_id).strip()
            
            print(f"Checking availability for platform: {platform}, user_id: {platform_user_id}, excluding_user: {current_user_id}")
            
            query = SocialMediaConnection.query.filter_by(
                platform=platform,
                platform_user_id=platform_user_id,
                is_active=True
            )
            
            # Exclude current user if provided (for updates)
            if current_user_id:
                query = query.filter(SocialMediaConnection.user_id != current_user_id)
            
            existing_connection = query.first()
            
            if existing_connection:
                print(f"Found existing connection: User {existing_connection.user_id} -> {existing_connection.platform_username}")
                return {
                    'available': False,
                    'connected_user_id': existing_connection.user_id,
                    'connected_username': existing_connection.platform_username
                }
            else:
                print(f"No existing connection found - account is available")
                return {
                    'available': True,
                    'connected_user_id': None,
                    'connected_username': None
                }
        except Exception as e:
            print(f"Error checking account availability: {e}")
            import traceback
            traceback.print_exc()
            
            # Rollback the transaction to prevent "transaction aborted" errors
            try:
                db.session.rollback()
                print("Rolled back transaction due to availability check error")
            except Exception as rollback_error:
                print(f"Error during rollback: {rollback_error}")
            
            # On error, default to available to allow connection (prevents false rejections)
            return {
                'available': True,  # Changed to True to prevent false rejections
                'connected_user_id': None,
                'connected_username': None,
                'error': str(e)
            }
    
    @staticmethod
    def create_connection(user_id, platform, platform_user_id, platform_username=None, 
                         access_token=None, refresh_token=None, token_expires_at=None, 
                         additional_data=None):
        """
        Create a new social media connection with exclusivity check
        
        Args:
            user_id (int): User ID
            platform (str): Platform name
            platform_user_id (str): Social media account ID
            platform_username (str, optional): Social media username
            access_token (str, optional): Access token
            refresh_token (str, optional): Refresh token
            token_expires_at (datetime, optional): Token expiration
            additional_data (dict, optional): Additional platform-specific data
            
        Returns:
            dict: {
                'success': bool,
                'connection': SocialMediaConnection or None,
                'error': str or None
            }
        """
        try:
            print(f"Creating connection for user {user_id}, platform {platform}, platform_user_id: {platform_user_id}")
            
            # Start a fresh transaction to avoid any previous transaction errors
            try:
                db.session.rollback()  # Clear any previous transaction state
            except Exception:
                pass  # Ignore rollback errors if no transaction is active
            
            # Enforce availability only for exclusive platforms
            if str(platform).lower() in ConnectionService.EXCLUSIVE_PLATFORMS:
                availability = ConnectionService.check_account_availability(
                    platform, platform_user_id, user_id
                )
                print(f"Availability check result: {availability}")
                if 'error' in availability:
                    print(f"Error in availability check: {availability['error']}")
                    print("Proceeding with connection due to availability check error")
                elif not availability['available']:
                    print(f"Account unavailable - already connected to user {availability['connected_user_id']}")
                    return {
                        'success': False,
                        'connection': None,
                        'error': 'account_unavailable',
                        'connected_username': availability['connected_username']
                    }
            
            # Check if user already has a connection for this platform (active or inactive)
            try:
                existing_user_connection = SocialMediaConnection.query.filter_by(
                    user_id=user_id,
                    platform=platform
                ).first()  # Remove is_active=True to find any existing connection
                
                # Also check if there's any existing connection with this platform_user_id (from any user)
                existing_platform_connection = SocialMediaConnection.query.filter_by(
                    platform=platform,
                    platform_user_id=platform_user_id
                ).first()  # This will find the duplicate that's causing the constraint violation
                
                print(f"DEBUG: Found existing user connection: {existing_user_connection}")
                print(f"DEBUG: Found existing platform connection: {existing_platform_connection}")
                
            except Exception as query_error:
                print(f"Error querying existing connection: {query_error}")
                db.session.rollback()
                existing_user_connection = None
                existing_platform_connection = None
            
            # Handle different scenarios for existing connections
            if existing_platform_connection:
                # There's already a connection with this platform_user_id
                if existing_platform_connection.user_id == user_id:
                    # Same user - just reactivate and update the existing connection
                    print(f"DEBUG: Reactivating existing connection for same user")
                    connection = existing_platform_connection
                    connection.is_active = True
                    connection.platform_username = platform_username
                    connection.access_token = access_token
                    connection.refresh_token = refresh_token
                    connection.token_expires_at = token_expires_at
                    connection.additional_data = json.dumps(additional_data) if additional_data else None
                    connection.updated_at = datetime.utcnow()
                else:
                    # Different user
                    if str(platform).lower() in ConnectionService.EXCLUSIVE_PLATFORMS:
                        # Block only for exclusive platforms
                        print(f"DEBUG: Platform account already connected to different user {existing_platform_connection.user_id}")
                        return {
                            'success': False,
                            'connection': None,
                            'error': 'account_unavailable',
                            'connected_username': existing_platform_connection.platform_username
                        }
                    else:
                        # For non-exclusive platforms, allow creating a new separate connection
                        print("DEBUG: Non-exclusive platform - allowing duplicate platform_user_id for different user")
                        connection = SocialMediaConnection(
                            user_id=user_id,
                            platform=platform,
                            platform_user_id=platform_user_id,
                            platform_username=platform_username,
                            access_token=access_token,
                            refresh_token=refresh_token,
                            token_expires_at=token_expires_at,
                            additional_data=json.dumps(additional_data) if additional_data else None
                        )
                        db.session.add(connection)
            elif existing_user_connection:
                # User has a connection for this platform but different platform_user_id
                print(f"DEBUG: Updating existing user connection with new platform account")
                connection = existing_user_connection
                connection.platform_user_id = platform_user_id
                connection.platform_username = platform_username
                connection.access_token = access_token
                connection.refresh_token = refresh_token
                connection.token_expires_at = token_expires_at
                connection.additional_data = json.dumps(additional_data) if additional_data else None
                connection.is_active = True
                connection.updated_at = datetime.utcnow()
            else:
                # Create new connection
                print(f"DEBUG: Creating completely new connection")
                connection = SocialMediaConnection(
                    user_id=user_id,
                    platform=platform,
                    platform_user_id=platform_user_id,
                    platform_username=platform_username,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_at=token_expires_at,
                    additional_data=json.dumps(additional_data) if additional_data else None
                )
                db.session.add(connection)
            
            print(f"DEBUG: About to commit connection to database...")
            db.session.commit()
            print(f"DEBUG: Successfully committed connection to database")
            
            return {
                'success': True,
                'connection': connection,
                'error': None
            }
            
        except IntegrityError as e:
            print(f"DEBUG: IntegrityError caught - this means account is already connected: {e}")
            db.session.rollback()
            return {
                'success': False,
                'connection': None,
                'error': 'account_unavailable',
                'connected_username': None
            }
        except Exception as e:
            print(f"DEBUG: General exception caught in create_connection: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return {
                'success': False,
                'connection': None,
                'error': str(e)
            }
    
    @staticmethod
    def disconnect_user_platform(user_id, platform):
        """
        Disconnect a user from a specific platform
        
        Args:
            user_id (int): User ID
            platform (str): Platform name
            
        Returns:
            dict: {
                'success': bool,
                'error': str or None
            }
        """
        try:
            connection = SocialMediaConnection.query.filter_by(
                user_id=user_id,
                platform=platform,
                is_active=True
            ).first()
            
            if connection:
                connection.is_active = False
                connection.updated_at = datetime.utcnow()
                db.session.commit()
                
                return {
                    'success': True,
                    'error': None
                }
            else:
                return {
                    'success': True,  # Already disconnected
                    'error': None
                }
                
        except Exception as e:
            db.session.rollback()
            print(f"Error disconnecting user platform: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_user_connection_status(user_id, platform):
        """
        Get connection status for a user and platform
        
        Args:
            user_id (int): User ID
            platform (str): Platform name
            
        Returns:
            dict: {
                'connected': bool,
                'username': str or None,
                'platform_user_id': str or None,
                'connection': SocialMediaConnection or None
            }
        """
        try:
            connection = SocialMediaConnection.query.filter_by(
                user_id=user_id,
                platform=platform,
                is_active=True
            ).first()
            
            if connection:
                return {
                    'connected': True,
                    'username': connection.platform_username,
                    'platform_user_id': connection.platform_user_id,
                    'connection': connection
                }
            else:
                return {
                    'connected': False,
                    'username': None,
                    'platform_user_id': None,
                    'connection': None
                }
                
        except Exception as e:
            print(f"Error getting user connection status: {e}")
            # Rollback transaction on error
            try:
                db.session.rollback()
            except Exception:
                pass
            return {
                'connected': False,
                'username': None,
                'platform_user_id': None,
                'connection': None,
                'error': str(e)
            }
    
    @staticmethod
    def get_all_user_connections(user_id):
        """
        Get all active connections for a user
        
        Args:
            user_id (int): User ID
            
        Returns:
            list: List of SocialMediaConnection objects
        """
        try:
            connections = SocialMediaConnection.query.filter_by(
                user_id=user_id,
                is_active=True
            ).all()
            
            return connections
            
        except Exception as e:
            print(f"Error getting user connections: {e}")
            return []
