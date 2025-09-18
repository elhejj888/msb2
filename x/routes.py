from flask import jsonify, request
import base64
import tempfile
import os
from jwt_utils import jwt_required_custom, get_current_user_from_token
from connection_service import ConnectionService

def setup_x_routes(app, get_x_manager):
    """Setup X (Twitter) routes with lazy manager initialization"""
    
    @app.route('/api/x/validate-credentials', methods=['GET'])
    def validate_x_credentials():
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({
                    'success': True,
                    'is_valid': False,
                    'error': 'X Manager not available'
                })
            
            is_valid = manager.validate_credentials()
            
            return jsonify({
                'success': True,
                'is_valid': is_valid
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/x/auth/start', methods=['POST'])
    @jwt_required_custom
    def start_x_auth(current_user=None, current_user_id=None):
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            # Read options
            force_login = False
            try:
                if request.is_json:
                    body = request.get_json(silent=True) or {}
                    force_login = bool(body.get('force_login', False))
            except Exception:
                force_login = False

            # Ensure per-user token context, and clear any existing token to force account selection
            try:
                manager.set_user_token_context(current_user_id)
                # Best-effort clear to avoid reusing previous account for this user
                # Also remove legacy global token file to prevent cross-user reuse
                print(f"[X] Starting OAuth for user_id={current_user_id}, token_file={manager.token_file}")
                manager.revoke_token(include_legacy=True)
            except Exception:
                pass

            # Start OAuth flow explicitly (opens browser and completes locally)
            success = bool(manager.start_oauth_flow(force_login=force_login))
            return jsonify({
                'success': success,
                'message': 'X (Twitter) authentication completed successfully' if success else 'Failed to complete X authentication'
            }), (200 if success else 500)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/x/auth/callback', methods=['POST'])
    def complete_x_auth():
        try:
            data = request.get_json()
            oauth_token = data.get('oauth_token')
            oauth_verifier = data.get('oauth_verifier')
            
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            # Complete the OAuth flow
            success = manager.complete_oauth_flow(oauth_token, oauth_verifier)
            
            return jsonify({
                'success': success,
                'message': 'Authentication completed successfully' if success else 'Authentication failed'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/create-tweet', methods=['POST'])
    def create_x_tweet():
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            data = request.get_json()
            
            text = data.get('text')
            image_base64 = data.get('image_base64')
            reply_to_tweet_id = data.get('reply_to_tweet_id')
            
            if not text:
                return jsonify({'success': False, 'error': 'Text is required'}), 400
            
            # Handle image upload if provided
            image_path = None
            if image_base64:
                try:
                    # Decode base64 image
                    image_data = base64.b64decode(image_base64.split(',')[1])
                    
                    # Create temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                        tmp_file.write(image_data)
                        image_path = tmp_file.name
                except Exception as e:
                    return jsonify({'success': False, 'error': f'Error processing image: {str(e)}'}), 400
            
            # Create the tweet
            tweet_data = manager.create_tweet(
                text=text,
                media_path=image_path,
                reply_to_tweet_id=reply_to_tweet_id
            )
            
            # Clean up temporary file
            if image_path and os.path.exists(image_path):
                os.unlink(image_path)
            
            if tweet_data:
                return jsonify({
                    'success': True,
                    'tweet': tweet_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to create tweet'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/tweets', methods=['GET'])
    def get_x_tweets():
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            limit = request.args.get('limit', 10, type=int)
            tweets = manager.get_user_tweets(limit=limit)
            
            # tweets will be an empty list if rate limited or other errors, never None
            return jsonify({
                'success': True,
                'tweets': tweets if tweets is not None else []
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/tweet/<tweet_id>', methods=['GET'])
    @jwt_required_custom
    def get_x_tweet(tweet_id, current_user=None, current_user_id=None):
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            tweet_data = manager.get_tweet(tweet_id)
            
            if tweet_data:
                return jsonify({
                    'success': True,
                    'tweet': tweet_data
                })
            else:
                return jsonify({'success': False, 'error': 'Tweet not found'}), 404
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/tweet/<tweet_id>', methods=['DELETE'])
    @jwt_required_custom
    def delete_x_tweet(tweet_id, current_user=None, current_user_id=None):
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            success = manager.delete_tweet(tweet_id)
            
            return jsonify({
                'success': success,
                'message': 'Tweet deleted successfully' if success else 'Failed to delete tweet'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/connection-status', methods=['GET'])
    @jwt_required_custom
    def get_x_connection_status(current_user=None, current_user_id=None):
        try:
            # Check database connection status first
            connection_status = ConnectionService.get_user_connection_status(current_user_id, 'x')
            
            if connection_status['connected']:
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': True,
                        'username': connection_status['username'],
                        'message': f'Connected to X (Twitter) as @{connection_status["username"]}' if connection_status['username'] else 'Connected to X (Twitter)'
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': False,
                        'message': 'Not connected to X (Twitter)'
                    }
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/connect', methods=['POST'])
    @jwt_required_custom
    def connect_x(current_user=None, current_user_id=None):
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            # Use per-user token context and load that user's tokens produced by OAuth start
            try:
                manager.set_user_token_context(current_user_id)
                print(f"[X] Connect route using user_id={current_user_id}, token_file={manager.token_file}")
                manager.load_tokens()
            except Exception:
                pass

            # Ensure we have an access token from the just-completed OAuth
            if not manager.auth.access_token:
                return jsonify({
                    'success': False,
                    'error': 'X (Twitter) authentication not completed. Please try connecting again.'
                }), 401

            # Get user info with retry and nuanced error handling to avoid false 401 on 429
            try:
                user_info = manager.get_user_info_with_retry()
                if not user_info:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to get user information from X (Twitter)'
                    }), 500
                if isinstance(user_info, dict) and user_info.get('error') == 'unauthorized':
                    return jsonify({
                        'success': False,
                        'error': 'X (Twitter) authentication invalid or expired. Please try connecting again.'
                    }), 401
                if isinstance(user_info, dict) and user_info.get('error') == 'rate_limited':
                    return jsonify({
                        'success': False,
                        'error': 'Rate limited by X (Twitter). Please wait a moment and try again.'
                    }), 429
                
                platform_user_id = str(user_info.get('id', ''))
                platform_username = user_info.get('username', '')
                
                print(f"X connection attempt - User: {current_user_id}, Platform User ID: {platform_user_id}, Username: {platform_username}")
                
                if not platform_user_id:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to get user ID from X (Twitter)'
                    }), 500
                
                # Check account exclusivity and create connection
                connection_result = ConnectionService.create_connection(
                    user_id=current_user_id,
                    platform='x',
                    platform_user_id=platform_user_id,
                    platform_username=platform_username,
                    access_token=manager.auth.access_token,
                    additional_data={
                        'access_token_secret': getattr(manager.auth, 'access_token_secret', None)
                    }
                )
                
                if connection_result['success']:
                    return jsonify({
                        'success': True,
                        'message': f'Successfully connected to X (Twitter) as @{platform_username}!',
                        'username': platform_username,
                        'connected': True
                    })
                else:
                    # Account exclusivity violation
                    if connection_result['error'] == 'account_unavailable':
                        return jsonify({
                            'success': False,
                            'error': 'This X (Twitter) account is already connected to another user',
                            'account_unavailable': True,
                            'connected_username': connection_result.get('connected_username')
                        }), 409
                    else:
                        return jsonify({
                            'success': False,
                            'error': f'Failed to save connection: {connection_result["error"]}'
                        }), 500
                        
            except Exception as e:
                print(f"Error processing X connection: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'error': f'Failed to process connection: {str(e)}'
                }), 500
        except Exception as e:
            print(f"Error in connect_x: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/disconnect', methods=['POST'])
    @jwt_required_custom
    def disconnect_x(current_user=None, current_user_id=None):
        try:
            # Remove DB connection first to reflect status immediately
            db_result = ConnectionService.disconnect_user_platform(current_user_id, 'x')
            
            # Clear tokens locally (best-effort)
            try:
                manager = get_x_manager()
                if manager:
                    # Ensure we remove only this user's token file
                    try:
                        manager.set_user_token_context(current_user_id)
                    except Exception:
                        pass
                    manager.revoke_token()
            except Exception:
                pass

            if db_result.get('success'):
                return jsonify({
                    'success': True,
                    'message': 'Successfully disconnected from X (Twitter)'
                })
            else:
                # If there was nothing to disconnect, still report success for idempotency
                return jsonify({
                    'success': True,
                    'message': db_result.get('message') or 'Disconnected (no active connection found)'
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/create-thread', methods=['POST'])
    def create_x_thread():
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            data = request.get_json()
            thread_tweets = data.get('thread_tweets', [])
            hashtags = data.get('hashtags', '')
            
            if not thread_tweets or len(thread_tweets) == 0:
                return jsonify({'success': False, 'error': 'Thread tweets are required'}), 400
            
            # Create thread using the manager
            thread_data = manager.create_thread(
                thread_tweets=thread_tweets,
                hashtags=hashtags
            )
            
            if thread_data:
                return jsonify({
                    'success': True,
                    'thread': thread_data,
                    'message': 'Thread created successfully'
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to create thread'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/schedule-tweet', methods=['POST'])
    def schedule_x_tweet():
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            data = request.get_json()
            
            text = data.get('text')
            scheduled_time = data.get('scheduled_time')
            hashtags = data.get('hashtags', '')
            image_base64 = data.get('image_base64')
            
            if not text:
                return jsonify({'success': False, 'error': 'Text is required'}), 400
            
            if not scheduled_time:
                return jsonify({'success': False, 'error': 'Scheduled time is required'}), 400
            
            # Handle image upload if provided
            image_path = None
            if image_base64:
                try:
                    # Decode base64 image
                    image_data = base64.b64decode(image_base64.split(',')[1])
                    
                    # Create temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                        tmp_file.write(image_data)
                        image_path = tmp_file.name
                except Exception as e:
                    return jsonify({'success': False, 'error': f'Error processing image: {str(e)}'}), 400
            
            # Schedule the tweet
            scheduled_data = manager.schedule_tweet(
                text=text,
                scheduled_time=scheduled_time,
                hashtags=hashtags,
                media_path=image_path
            )
            
            # Clean up temporary file
            if image_path and os.path.exists(image_path):
                os.unlink(image_path)
            
            if scheduled_data:
                return jsonify({
                    'success': True,
                    'scheduled_tweet': scheduled_data,
                    'message': 'Tweet scheduled successfully'
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to schedule tweet'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/insights/<tweet_id>', methods=['GET'])
    def get_x_tweet_insights(tweet_id):
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            insights_data = manager.get_tweet_insights(tweet_id)
            
            if insights_data:
                return jsonify({
                    'success': True,
                    'insights': insights_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to fetch insights or tweet not found'}), 404
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/insights/summary', methods=['GET'])
    def get_x_insights_summary():
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            days = request.args.get('days', 30, type=int)
            
            summary_data = manager.get_insights_summary(days=days)
            
            if summary_data:
                return jsonify({
                    'success': True,
                    'summary': summary_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to fetch insights summary'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/hashtags/trending', methods=['GET'])
    def get_trending_hashtags():
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            trending_data = manager.get_trending_hashtags()
            
            if trending_data:
                return jsonify({
                    'success': True,
                    'trending_hashtags': trending_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to fetch trending hashtags'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500