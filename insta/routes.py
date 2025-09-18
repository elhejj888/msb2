from flask import jsonify, request
from .controller import InstagramManager
from .models import InstagramPost

def setup_routes(app):
    instagram_manager = InstagramManager()

    @app.route('/api/instagram/validate-credentials', methods=['GET'])
    def validate_instagram_credentials():
        try:
            is_valid = instagram_manager.validate_credentials()
            return jsonify({'success': True, 'is_valid': is_valid})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/instagram/create-post', methods=['POST'])
    def create_instagram_post():
        try:
            data = request.get_json()
            
            caption = data.get('caption', '')
            image_base64 = data.get('image_base64')
            carousel_images_base64 = data.get('carousel_images', [])
            
            if not caption and not (image_base64 or carousel_images_base64):
                return jsonify({'success': False, 'error': 'Either caption or image(s) are required'}), 400
            
            # Handle single image upload if provided
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
            
            # Handle carousel images if provided
            carousel_images = []
            if carousel_images_base64:
                try:
                    for img_base64 in carousel_images_base64:
                        img_data = base64.b64decode(img_base64.split(',')[1])
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                            tmp_file.write(img_data)
                            carousel_images.append(tmp_file.name)
                except Exception as e:
                    # Clean up any created files
                    for img_path in carousel_images:
                        if os.path.exists(img_path):
                            os.unlink(img_path)
                    if image_path and os.path.exists(image_path):
                        os.unlink(image_path)
                    return jsonify({'success': False, 'error': f'Error processing carousel images: {str(e)}'}), 400
            
            # Create the post
            if carousel_images:
                post_data = instagram_manager.create_post(
                    caption=caption,
                    carousel_images=carousel_images
                )
            else:
                post_data = instagram_manager.create_post(
                    caption=caption,
                    image_path=image_path
                )
            
            # Clean up temporary files
            if image_path and os.path.exists(image_path):
                os.unlink(image_path)
            for img_path in carousel_images:
                if os.path.exists(img_path):
                    os.unlink(img_path)
            
            if post_data:
                return jsonify({
                    'success': True,
                    'post': post_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to create post'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/instagram/posts', methods=['GET'])
    def get_instagram_posts():
        try:
            limit = request.args.get('limit', 10, type=int)
            posts = instagram_manager.get_user_posts(limit=limit)
            
            if posts is not None:
                return jsonify({
                    'success': True,
                    'posts': posts
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve posts'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/instagram/post/<post_id>', methods=['GET'])
    def get_instagram_post(post_id):
        try:
            post_data = instagram_manager.read_post(post_id)
            
            if post_data:
                return jsonify({
                    'success': True,
                    'post': post_data
                })
            else:
                return jsonify({'success': False, 'error': 'Post not found'}), 404
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/instagram/post/<post_id>', methods=['DELETE'])
    def delete_instagram_post(post_id):
        try:
            success = instagram_manager.delete_post(post_id)
            
            return jsonify({
                'success': success,
                'message': 'Post deleted successfully' if success else 'Failed to delete post'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500