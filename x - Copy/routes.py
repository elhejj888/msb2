from flask import jsonify, request
import base64
import tempfile
import os

def setup_x_routes(app, get_x_manager):
    """Setup X (Twitter) routes with simplified authentication"""
    
    @app.route('/api/x/validate-credentials', methods=['GET'])
    def validate_x_credentials():
        """Validate X credentials"""
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({
                    'success': False,
                    'is_valid': False,
                    'error': 'X Manager not available'
                })
            
            is_valid = manager.validate_credentials()
            
            return jsonify({
                'success': True,
                'is_valid': is_valid,
                'message': 'X credentials are valid' if is_valid else 'X credentials are invalid or expired'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/x/auth/start', methods=['POST'])
    def start_x_auth():
        """Start X authentication process"""
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            # Start the authentication process
            success = manager.start_authentication()
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'X authentication started successfully',
                    'auth_url': 'http://localhost:8081/callback'  # Add this line
                })
            else:
                return jsonify({
                    'success': False, 
                    'error': 'X authentication failed',
                    'message': 'Please check your X API credentials and try again'
                }), 400
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/x/auth/callback', methods=['POST'])
    def x_complete_auth():
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
            
            if tweets is not None:
                return jsonify({
                    'success': True,
                    'tweets': tweets
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve tweets'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/x/tweet/<tweet_id>', methods=['GET'])
    def get_x_tweet(tweet_id):
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
    def delete_x_tweet(tweet_id):
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
    
    @app.route('/api/x/auth/disconnect', methods=['POST'])
    def disconnect_x():
        try:
            manager = get_x_manager()
            if not manager:
                return jsonify({'success': False, 'error': 'X Manager not available'}), 500
            
            # Clear tokens
            manager.auth.access_token = None
            manager.auth.refresh_token = None
            
            # Delete token file
            if os.path.exists(manager.auth.token_file):
                os.unlink(manager.auth.token_file)
                
            return jsonify({
                'success': True,
                'message': 'Successfully disconnected from X'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500