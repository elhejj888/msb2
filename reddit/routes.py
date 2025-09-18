from flask import jsonify, request
import base64
import tempfile
import os
from jwt_utils import jwt_required_custom, get_current_user_from_token
from connection_service import ConnectionService

def setup_reddit_routes(app, reddit_manager):
    @app.route('/api/reddit/connection-status', methods=['GET'])
    @jwt_required_custom
    def get_connection_status(current_user=None, current_user_id=None):
        try:
            # Ensure manager uses per-user credentials path
            try:
                reddit_manager.configure_for_user(current_user_id)
            except Exception as _cfg_err:
                print(f"DEBUG: Failed to configure Reddit manager for user {current_user_id}: {_cfg_err}")
            # Check database connection status first
            connection_status = ConnectionService.get_user_connection_status(current_user_id, 'reddit')
            
            if connection_status['connected']:
                # Validate that the Reddit tokens are still valid
                connection = connection_status.get('connection')
                if connection and hasattr(connection, 'access_token'):
                    refresh_token = connection.access_token  # This is actually the refresh token for Reddit
                    
                    if refresh_token:
                        try:
                            # Try to validate the token by creating a Reddit instance
                            import praw
                            import prawcore.exceptions
                            
                            test_reddit = praw.Reddit(
                                client_id=reddit_manager.auth.client_id,
                                client_secret=reddit_manager.auth.client_secret,
                                refresh_token=refresh_token,
                                user_agent="RedditCRUDAutomation/1.0"
                            )
                            
                            # Test the connection
                            user_info = test_reddit.user.me()
                            
                            # If successful, update the reddit_manager state
                            reddit_manager.reddit = test_reddit
                            reddit_manager.auth.reddit = test_reddit
                            reddit_manager.authenticated = True
                            
                            return jsonify({
                                'success': True,
                                'status': {
                                    'connected': True,
                                    'username': connection_status['username'],
                                    'message': f'Connected to Reddit as u/{connection_status["username"]}' if connection_status['username'] else 'Connected to Reddit'
                                }
                            })
                            
                        except (prawcore.exceptions.ResponseException, prawcore.exceptions.OAuthException) as token_error:
                            print(f"DEBUG: Reddit token validation failed: {token_error}")
                            
                            # Token is invalid, clear the connection from database
                            try:
                                ConnectionService.disconnect_user_platform(current_user_id, 'reddit')
                                print("DEBUG: Cleared invalid Reddit connection from database")
                            except Exception as clear_error:
                                print(f"DEBUG: Failed to clear invalid connection: {clear_error}")
                            
                            # Reset reddit manager state
                            reddit_manager.reddit = None
                            reddit_manager.auth.reddit = None
                            reddit_manager.authenticated = False
                            
                            return jsonify({
                                'success': True,
                                'status': {
                                    'connected': False,
                                    'message': 'Reddit connection expired. Please reconnect your account.'
                                }
                            })
                            
                        except Exception as validation_error:
                            print(f"DEBUG: Error validating Reddit connection: {validation_error}")
                            return jsonify({
                                'success': True,
                                'status': {
                                    'connected': False,
                                    'message': 'Reddit connection could not be validated. Please reconnect your account.'
                                }
                            })
                
                # If no valid token found, return connected status from database
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': True,
                        'username': connection_status['username'],
                        'message': f'Connected to Reddit as u/{connection_status["username"]}' if connection_status['username'] else 'Connected to Reddit'
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': False,
                        'message': 'Not connected to Reddit'
                    }
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/connect', methods=['POST'])
    @jwt_required_custom
    def connect_reddit(current_user=None, current_user_id=None):
        try:
            # Configure manager for this user so OAuth tokens are stored per-user
            try:
                reddit_manager.configure_for_user(current_user_id)
            except Exception as _cfg_err:
                print(f"DEBUG: Failed to configure Reddit manager for user {current_user_id}: {_cfg_err}")

            success, message = reddit_manager.connect_reddit_account(user_id=current_user_id)
            
            if success:
                # Get user info from Reddit API to check account exclusivity
                try:
                    user_info = reddit_manager.get_user_info()  # This should return user ID and username
                    if not user_info:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to get user information from Reddit'
                        }), 500
                    
                    platform_user_id = str(user_info.get('id', ''))
                    platform_username = user_info.get('name', '')  # Reddit uses 'name' for username
                    
                    print(f"Reddit connection attempt - User: {current_user_id}, Platform User ID: {platform_user_id}, Username: {platform_username}")
                    
                    if not platform_user_id:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to get user ID from Reddit'
                        }), 500
                    
                    # Check account exclusivity and create connection
                    # Reddit uses refresh tokens, not access tokens
                    refresh_token = None
                    if hasattr(reddit_manager, 'auth') and reddit_manager.auth:
                        # Get refresh token from saved credentials
                        saved_creds = reddit_manager.auth.load_credentials()
                        if saved_creds:
                            refresh_token = saved_creds.get('refresh_token')
                    
                    connection_result = ConnectionService.create_connection(
                        user_id=current_user_id,
                        platform='reddit',
                        platform_user_id=platform_user_id,
                        platform_username=platform_username,
                        access_token=refresh_token,  # Store refresh token as access_token for Reddit
                        additional_data={
                            'refresh_token': refresh_token,
                            'client_id': reddit_manager.auth.client_id if hasattr(reddit_manager, 'auth') else None,
                            'client_secret': reddit_manager.auth.client_secret if hasattr(reddit_manager, 'auth') else None
                        }
                    )
                    
                    if connection_result['success']:
                        return jsonify({
                            'success': True,
                            'message': f'Successfully connected to Reddit as u/{platform_username}!',
                            'username': platform_username
                        })
                    else:
                        # Account exclusivity violation
                        if connection_result['error'] == 'account_unavailable':
                            return jsonify({
                                'success': False,
                                'error': 'This Reddit account is already connected to another user',
                                'account_unavailable': True,
                                'connected_username': connection_result.get('connected_username')
                            }), 409
                        else:
                            return jsonify({
                                'success': False,
                                'error': f'Failed to save connection: {connection_result["error"]}'
                            }), 500
                            
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to process connection: {str(e)}'
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'message': message
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/disconnect', methods=['POST'])
    @jwt_required_custom
    def disconnect_reddit(current_user=None, current_user_id=None):
        try:
            # Disconnect from database first
            disconnect_result = ConnectionService.disconnect_user_platform(current_user_id, 'reddit')
            
            if disconnect_result['success']:
                # Also try to disconnect from Reddit manager if available
                try:
                    # Ensure manager uses per-user credentials path
                    try:
                        reddit_manager.configure_for_user(current_user_id)
                    except Exception as _cfg_err:
                        print(f"DEBUG: Failed to configure Reddit manager for user {current_user_id}: {_cfg_err}")
                    success, message = reddit_manager.disconnect_reddit_account(user_id=current_user_id)
                except Exception as e:
                    print(f"Warning: Failed to disconnect from Reddit manager: {e}")
                
                return jsonify({
                    'success': True,
                    'message': 'Successfully disconnected from Reddit'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to disconnect: {disconnect_result["error"]}'
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/validate-subreddit', methods=['POST'])
    def validate_subreddit():
        try:
            data = request.get_json()
            subreddit_name = data.get('subreddit_name')
            
            if not subreddit_name:
                return jsonify({'success': False, 'error': 'Subreddit name is required'}), 400
            
            is_valid, clean_name = reddit_manager.validate_subreddit(subreddit_name)
            
            return jsonify({
                'success': True,
                'is_valid': is_valid,
                'clean_name': clean_name
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/create-post', methods=['POST'])
    def create_reddit_post():
        try:
            data = request.get_json()
            
            subreddit_name = data.get('subreddit_name')
            title = data.get('title')
            content = data.get('content', '')
            image_base64 = data.get('image_base64')
            is_spoiler = data.get('is_spoiler', False)
            nsfw = data.get('nsfw', False)
            
            if not subreddit_name or not title:
                return jsonify({'success': False, 'error': 'Subreddit name and title are required'}), 400
            
            image_path = None
            if image_base64:
                try:
                    image_data = base64.b64decode(image_base64.split(',')[1])
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                        tmp_file.write(image_data)
                        image_path = tmp_file.name
                except Exception as e:
                    return jsonify({'success': False, 'error': f'Error processing image: {str(e)}'}), 400
            
            submission = reddit_manager.create_post(
                subreddit_name=subreddit_name,
                title=title,
                content=content,
                image_path=image_path,
                is_spoiler=is_spoiler,
                nsfw=nsfw
            )
            
            if image_path and os.path.exists(image_path):
                os.unlink(image_path)
            
            if submission:
                return jsonify({
                    'success': True,
                    'post': {
                        'id': submission.id,
                        'url': submission.url,
                        'permalink': f"https://www.reddit.com{submission.permalink}",
                        'title': submission.title
                    }
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to create post'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/posts/<subreddit_name>', methods=['GET'])
    def get_subreddit_posts(subreddit_name):
        try:
            limit = request.args.get('limit', 20, type=int)
            posts = reddit_manager.get_subreddit_posts(subreddit_name, limit=limit)
            
            return jsonify({
                'success': True,
                'posts': posts
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/post/<post_id>', methods=['GET'])
    def get_reddit_post(post_id):
        try:
            post_data = reddit_manager.read_post(post_id=post_id)
            
            if post_data:
                return jsonify({
                    'success': True,
                    'post': post_data
                })
            else:
                return jsonify({'success': False, 'error': 'Post not found'}), 404
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/user-posts', methods=['GET'])
    def get_user_reddit_posts():
        try:
            # Manual JWT validation for debugging
            auth_header = request.headers.get('Authorization')
            print(f"DEBUG: Authorization header: {auth_header}")
            
            if not auth_header or not auth_header.startswith('Bearer '):
                print("DEBUG: No valid Authorization header found")
                return jsonify({'success': False, 'error': 'No valid authorization header'}), 401
            
            token = auth_header.split(' ')[1]
            print(f"DEBUG: Extracted token: {token[:50]}...")
            
            # Try to validate token manually
            try:
                from flask_jwt_extended import decode_token
                decoded_token = decode_token(token)
                current_user_id = decoded_token['sub']
                print(f"DEBUG: Decoded user ID: {current_user_id}")
            except Exception as jwt_error:
                print(f"DEBUG: JWT validation error: {jwt_error}")
                return jsonify({'success': False, 'error': f'Invalid token: {str(jwt_error)}'}), 401
            
            # Check database connection status first and restore Reddit manager authentication
            from connection_service import ConnectionService
            connection_status = ConnectionService.get_user_connection_status(current_user_id, 'reddit')
            print(f"DEBUG: Database connection status: {connection_status}")
            
            # Configure manager for this user for per-user token storage
            try:
                reddit_manager.configure_for_user(current_user_id)
            except Exception as _cfg_err:
                print(f"DEBUG: Failed to configure Reddit manager for user {current_user_id}: {_cfg_err}")

            if not connection_status['connected']:
                print("DEBUG: User not connected to Reddit in database")
                return jsonify({
                    'success': False,
                    'error': 'Not connected to Reddit. Please connect your account first.',
                    'posts': []
                }), 401
            
            # Try to restore Reddit manager authentication from database
            try:
                # Get connection details from database
                connection = connection_status.get('connection')
                if connection and hasattr(connection, 'access_token'):
                    print("DEBUG: Attempting to restore Reddit authentication from database...")
                    
                    # Get refresh token from database connection
                    refresh_token = connection.access_token  # This is actually the refresh token for Reddit
                    print(f"DEBUG: Found refresh token in database: {refresh_token[:20] if refresh_token else 'None'}...")
                    
                    if refresh_token:
                        # Manually restore Reddit connection using database credentials
                        import praw
                        import prawcore.exceptions
                        
                        try:
                            reddit_manager.reddit = praw.Reddit(
                                client_id=reddit_manager.auth.client_id,
                                client_secret=reddit_manager.auth.client_secret,
                                refresh_token=refresh_token,
                                user_agent="RedditCRUDAutomation/1.0"
                            )
                            reddit_manager.auth.reddit = reddit_manager.reddit
                            
                            # Verify the connection works
                            try:
                                user_info = reddit_manager.reddit.user.me()
                                reddit_manager.authenticated = True
                                print(f"DEBUG: Successfully restored Reddit connection for user: {user_info.name}")
                            except (prawcore.exceptions.ResponseException, prawcore.exceptions.OAuthException) as verify_error:
                                print(f"DEBUG: Reddit token expired or invalid: {verify_error}")
                                reddit_manager.reddit = None
                                reddit_manager.auth.reddit = None
                                reddit_manager.authenticated = False
                                
                                # Clear the invalid connection from database
                                try:
                                    ConnectionService.disconnect_user_platform(current_user_id, 'reddit')
                                    print("DEBUG: Cleared invalid Reddit connection from database")
                                except Exception as clear_error:
                                    print(f"DEBUG: Failed to clear invalid connection: {clear_error}")
                                    
                        except Exception as praw_error:
                            print(f"DEBUG: Failed to create Reddit instance: {praw_error}")
                            reddit_manager.reddit = None
                            reddit_manager.auth.reddit = None
                            reddit_manager.authenticated = False
                    
                    print(f"DEBUG: Reddit manager is_authenticated after restore: {reddit_manager.is_authenticated()}")
            except Exception as restore_error:
                print(f"DEBUG: Error restoring Reddit authentication: {restore_error}")
            
            # Check if Reddit manager is authenticated after restoration attempt
            is_authenticated = reddit_manager.is_authenticated()
            print(f"DEBUG: Final Reddit manager is_authenticated: {is_authenticated}")
            
            if not is_authenticated:
                print("DEBUG: Reddit manager still not authenticated after restoration attempt")
                return jsonify({
                    'success': False,
                    'error': 'Reddit authentication could not be restored. Please reconnect your account.',
                    'posts': []
                }), 401
            
            limit = request.args.get('limit', 20, type=int)
            posts = reddit_manager.get_user_posts(limit=limit)
            
            clean_posts = []
            for post in posts:
                clean_post = {k: v for k, v in post.items() if k != 'submission'}
                clean_posts.append(clean_post)
            
            return jsonify({
                'success': True,
                'posts': clean_posts
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/post/<post_id>', methods=['PUT'])
    @jwt_required_custom
    def update_reddit_post(post_id, current_user=None, current_user_id=None):
        try:
            data = request.get_json()
            
            new_content = data.get('new_content')
            mark_nsfw = data.get('mark_nsfw')
            mark_spoiler = data.get('mark_spoiler')
            
            success = reddit_manager.update_post(
                post_id=post_id,
                new_content=new_content,
                mark_nsfw=mark_nsfw,
                mark_spoiler=mark_spoiler
            )
            
            return jsonify({
                'success': success,
                'message': 'Post updated successfully' if success else 'Failed to update post'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/reddit/post/<post_id>', methods=['DELETE'])
    @jwt_required_custom
    def delete_reddit_post(post_id, current_user=None, current_user_id=None):
        try:
            success = reddit_manager.delete_post(post_id=post_id)
            
            return jsonify({
                'success': success,
                'message': 'Post deleted successfully' if success else 'Failed to delete post'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500