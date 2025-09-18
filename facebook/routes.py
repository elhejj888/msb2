from flask import jsonify, request
from .controller import FacebookManager

from flask import jsonify, request

def setup_facebook_routes(app, facebook_manager): 
    @app.route('/api/facebook/validate-credentials', methods=['GET'])
    def validate_facebook_credentials():
        try:
            is_valid = facebook_manager.validate_credentials()
            return jsonify({
                'success': True,
                'is_valid': is_valid
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/facebook/create-post', methods=['POST'])
    def create_facebook_post():
        try:
            data = request.get_json()
            message = data.get('message')
            link = data.get('link')
            image_base64 = data.get('image_base64')
            scheduled_time = data.get('scheduled_time')
            
            if not message:
                return jsonify({'success': False, 'error': 'Message is required'}), 400
            
            image_path = None
            if image_base64:
                try:
                    import base64
                    import tempfile
                    image_data = base64.b64decode(image_base64.split(',')[1])
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                        tmp_file.write(image_data)
                        image_path = tmp_file.name
                except Exception as e:
                    return jsonify({'success': False, 'error': f'Error processing image: {str(e)}'}), 400
            
            post_data = facebook_manager.create_post(
                message=message,
                link=link,
                image_path=image_path,
                scheduled_time=scheduled_time
            )
            
            if image_path:
                import os
                os.unlink(image_path)
            
            if post_data:
                return jsonify({
                    'success': True,
                    'post': post_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to create post'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/facebook/posts', methods=['GET'])
    def get_facebook_posts():
        try:
            limit = request.args.get('limit', 10, type=int)
            posts = facebook_manager.get_page_posts(limit=limit)
            
            if posts is not None:
                return jsonify({
                    'success': True,
                    'posts': posts
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve posts'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/facebook/post/<post_id>', methods=['GET'])
    def get_facebook_post(post_id):
        try:
            post_data = facebook_manager.read_post(post_id)
            
            if post_data:
                return jsonify({
                    'success': True,
                    'post': post_data
                })
            else:
                return jsonify({'success': False, 'error': 'Post not found'}), 404
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/facebook/post/<post_id>', methods=['PUT'])
    def update_facebook_post(post_id):
        try:
            data = request.get_json()
            new_message = data.get('new_message')
            link = data.get('link')
            
            success = facebook_manager.update_post(
                post_id=post_id,
                new_message=new_message,
                link=link
            )
            
            return jsonify({
                'success': success,
                'message': 'Post updated successfully' if success else 'Failed to update post'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/facebook/post/<post_id>', methods=['DELETE'])
    def delete_facebook_post(post_id):
        try:
            success = facebook_manager.delete_post(post_id)
            return jsonify({
                'success': True,
                'message': 'Post deleted successfully' if success else 'Failed to delete post'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500