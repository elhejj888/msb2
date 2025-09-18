from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from .analytics_manager import AnalyticsManager
from datetime import datetime, timedelta
from sqlalchemy import text
import logging
import traceback
import jwt as jwt_lib
from flask import current_app

logger = logging.getLogger(__name__)

def setup_analytics_routes(app, db):
    """
    Setup analytics routes for comprehensive data analysis and visualization
    """
    
    analytics_manager = AnalyticsManager(db)
    
    # Debug: Check if JWT manager is available
    logger.info(f"Analytics routes setup - App has JWT manager: {hasattr(app, 'jwt_manager')}")
    logger.info(f"Analytics routes setup - App config JWT_SECRET_KEY: {app.config.get('JWT_SECRET_KEY', 'NOT_SET')}")
    
    # Test endpoint without JWT to verify basic functionality
    @app.route('/api/analytics/test-basic', methods=['GET'])
    def test_basic():
        return jsonify({
            'success': True,
            'message': 'Analytics basic endpoint working',
            'jwt_config': {
                'jwt_secret_key_set': bool(app.config.get('JWT_SECRET_KEY')),
                'jwt_manager_exists': hasattr(app, 'jwt_manager'),
                'jwt_secret_preview': str(app.config.get('JWT_SECRET_KEY', 'NOT_SET'))[:10] + '...' if app.config.get('JWT_SECRET_KEY') else 'NOT_SET'
            }
        })
    
    # Test endpoint to verify JWT authentication is working
    @app.route('/api/analytics/test-auth', methods=['GET'])
    def test_analytics_auth():
        """Test analytics authentication with detailed debugging"""
        try:
            logger.info("Analytics auth test endpoint called")
            
            # Get the Authorization header
            auth_header = request.headers.get('Authorization')
            logger.info(f"Authorization header: {auth_header[:50] if auth_header else 'None'}...")
            
            if not auth_header:
                return jsonify({
                    'success': False,
                    'error': 'No Authorization header found',
                    'authenticated': False
                }), 401
            
            if not auth_header.startswith('Bearer '):
                return jsonify({
                    'success': False,
                    'error': 'Authorization header must start with Bearer',
                    'authenticated': False
                }), 401
            
            # Extract token
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            logger.info(f"Token extracted: {token[:20]}...")
            
            # Verify JWT token manually first
            try:
                # Decode without verification to check payload
                unverified_payload = jwt_lib.decode(token, options={"verify_signature": False})
                logger.info(f"Token payload: {unverified_payload}")
                
                # Check if token is expired
                import time
                current_time = time.time()
                exp_time = unverified_payload.get('exp', 0)
                
                if current_time > exp_time:
                    return jsonify({
                        'success': False,
                        'error': 'Token has expired',
                        'authenticated': False,
                        'exp_time': exp_time,
                        'current_time': current_time
                    }), 401
                
                # Now verify with Flask-JWT-Extended
                verify_jwt_in_request()
                user_id = get_jwt_identity()
                logger.info(f"Analytics auth test successful for user: {user_id}")
                
                # Get basic user info from database
                from models import User
                # Convert string user_id back to int for database query
                user = User.query.get(int(user_id))
                
                user_info = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                } if user else {'id': user_id}
                
                return jsonify({
                    'success': True,
                    'message': 'Analytics authentication successful',
                    'authenticated': True,
                    'user': user_info,
                    'timestamp': datetime.now().isoformat()
                })
                
            except jwt_lib.ExpiredSignatureError:
                return jsonify({
                    'success': False,
                    'error': 'Token has expired',
                    'authenticated': False
                }), 401
            except jwt_lib.InvalidTokenError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid token: {str(e)}',
                    'authenticated': False
                }), 401
            
        except Exception as e:
            logger.error(f"Analytics auth test error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({
                'success': False,
                'error': f'Auth test failed: {str(e)}',
                'authenticated': False
            }), 500
    
    @app.route('/api/analytics/platform-usage', methods=['GET'])
    def get_platform_usage_statistics():
        """
        Get comprehensive platform usage statistics
        Returns data for pie charts, bar charts, and platform rankings
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            # Optional period filters
            start_arg = request.args.get('start_date')
            end_arg = request.args.get('end_date')
            start_date = None
            end_date = None
            if start_arg and end_arg:
                try:
                    start_date = datetime.fromisoformat(start_arg)
                    end_date = datetime.fromisoformat(end_arg)
                except Exception:
                    start_date = None
                    end_date = None
            data = analytics_manager.get_platform_usage_statistics(start_date, end_date)
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error in platform usage statistics: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/analytics/predictions', methods=['GET'])
    def get_predictions():
        """Predictive analytics for admin dashboard with optional date filters"""
        try:
            verify_jwt_in_request()
            _uid = get_jwt_identity()
            start_arg = request.args.get('start_date')
            end_arg = request.args.get('end_date')
            start_date = None
            end_date = None
            if start_arg and end_arg:
                try:
                    start_date = datetime.fromisoformat(start_arg)
                    end_date = datetime.fromisoformat(end_arg)
                except Exception:
                    start_date = None
                    end_date = None
            data = analytics_manager.get_predictions(start_date, end_date)
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            logger.error(f"Error in predictions endpoint: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/analytics/user-engagement', methods=['GET'])
    def get_user_engagement_metrics():
        """
        Get user engagement metrics and active user statistics
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            # Optional period filters
            start_arg = request.args.get('start_date')
            end_arg = request.args.get('end_date')
            start_date = None
            end_date = None
            if start_arg and end_arg:
                try:
                    start_date = datetime.fromisoformat(start_arg)
                    end_date = datetime.fromisoformat(end_arg)
                except Exception:
                    start_date = None
                    end_date = None
            data = analytics_manager.get_user_engagement_metrics(start_date, end_date)
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error in user engagement metrics: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/analytics/temporal-trends', methods=['GET'])
    def get_temporal_trends():
        """
        Get temporal trends and patterns for trend charts
        Supports optional 'days' parameter for custom time ranges
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            days = request.args.get('days', 30, type=int)
            if days < 1 or days > 365:
                days = 30  # Default to 30 days if invalid
            
            data = analytics_manager.get_temporal_trends(days)
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error in temporal trends: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/analytics/user-activity/<int:user_id>', methods=['GET'])
    def get_user_activity_history(user_id):
        """
        Get detailed activity history for a specific user
        Shows platform-specific activity and statistics
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            
            # Users can only access their own data unless they're admin
            # For now, allow access to requested user_id (you can add admin check later)
            
            data = analytics_manager.get_user_activity_history(user_id)
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error in user activity history: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/analytics/my-activity', methods=['GET'])
    def get_my_activity_history():
        """
        Get activity history for the currently logged-in user
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            # Convert string user_id back to int for database query
            data = analytics_manager.get_user_activity_history(int(current_user_id))
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error in my activity history: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/analytics/content-analysis', methods=['GET'])
    def get_content_analysis():
        """
        Get content analysis and patterns across platforms
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            data = analytics_manager.get_content_analysis()
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error in content analysis: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/analytics/dashboard', methods=['GET'])
    def get_comprehensive_dashboard_data():
        """
        Get all analytics data for the dashboard in a single API call
        Includes user-specific data if user_id is provided
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            include_user_data = request.args.get('include_user_data', 'true').lower() == 'true'
            start_arg = request.args.get('start_date')
            end_arg = request.args.get('end_date')
            start_date = None
            end_date = None
            if start_arg and end_arg:
                try:
                    start_date = datetime.fromisoformat(start_arg)
                    end_date = datetime.fromisoformat(end_arg)
                except Exception:
                    start_date = None
                    end_date = None
            
            # Convert string user_id back to int for database query
            user_id_for_data = int(user_id) if include_user_data else None
            data = analytics_manager.get_comprehensive_dashboard_data(user_id_for_data, start_date, end_date)
            
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error in comprehensive dashboard data: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/analytics/platform-comparison', methods=['GET'])
    def get_platform_comparison():
        """
        Get detailed platform comparison data for advanced analytics
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            platform_stats = analytics_manager.get_platform_usage_statistics()
            user_engagement = analytics_manager.get_user_engagement_metrics()
            
            # Create comparison metrics
            comparison_data = {
                'platform_rankings': platform_stats.get('platform_rankings', []),
                'success_rates': {},
                'user_distribution': {},
                'activity_scores': {}
            }
            
            if 'platform_statistics' in platform_stats:
                for platform, stats in platform_stats['platform_statistics'].items():
                    comparison_data['success_rates'][platform] = stats.get('success_rate', 0)
                    comparison_data['user_distribution'][platform] = stats.get('unique_users', 0)
                    comparison_data['activity_scores'][platform] = stats.get('activity_score', 0)
            
            return jsonify({
                'success': True,
                'data': comparison_data
            })
        except Exception as e:
            logger.error(f"Error in platform comparison: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/analytics/real-time-stats', methods=['GET'])
    def get_real_time_statistics():
        """
        Get real-time statistics for live dashboard updates
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            from datetime import datetime, timedelta
            from sqlalchemy import text
            
            # Get statistics for the last 24 hours
            yesterday = datetime.now() - timedelta(days=1)
            
            real_time_stats = {
                'last_24_hours': {},
                'current_active_users': 0,
                'recent_posts': []
            }
            
            # Get posts from last 24 hours for each platform
            for platform in analytics_manager.platforms:
                table_name = analytics_manager.table_mapping[platform]
                
                query = text(f"""
                    SELECT COUNT(*) as posts_count
                    FROM {table_name}
                    WHERE created_at >= :yesterday
                """)
                
                result = db.session.execute(query, {'yesterday': yesterday}).fetchone()
                real_time_stats['last_24_hours'][platform] = result.posts_count or 0
            
            # Get recent posts across all platforms
            recent_posts_query = text("""
                SELECT 'instagram' as platform, created_at, user_id FROM instagram_posts WHERE created_at >= :yesterday
                UNION ALL
                SELECT 'facebook' as platform, created_at, user_id FROM facebook_posts WHERE created_at >= :yesterday
                UNION ALL
                SELECT 'x' as platform, created_at, user_id FROM x_posts WHERE created_at >= :yesterday
                UNION ALL
                SELECT 'reddit' as platform, created_at, user_id FROM reddit_posts WHERE created_at >= :yesterday
                UNION ALL
                SELECT 'pinterest' as platform, created_at, user_id FROM pinterest_posts WHERE created_at >= :yesterday
                UNION ALL
                SELECT 'youtube' as platform, created_at, user_id FROM youtube_posts WHERE created_at >= :yesterday
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            recent_results = db.session.execute(recent_posts_query, {'yesterday': yesterday}).fetchall()
            
            real_time_stats['recent_posts'] = [
                {
                    'platform': result.platform,
                    'created_at': result.created_at.isoformat(),
                    'user_id': result.user_id
                } for result in recent_results
            ]
            
            # Get active users count (users who posted in last 24 hours)
            active_users_query = text("""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM (
                    SELECT user_id FROM instagram_posts WHERE created_at >= :yesterday
                    UNION
                    SELECT user_id FROM facebook_posts WHERE created_at >= :yesterday
                    UNION
                    SELECT user_id FROM x_posts WHERE created_at >= :yesterday
                    UNION
                    SELECT user_id FROM reddit_posts WHERE created_at >= :yesterday
                    UNION
                    SELECT user_id FROM pinterest_posts WHERE created_at >= :yesterday
                    UNION
                    SELECT user_id FROM youtube_posts WHERE created_at >= :yesterday
                ) as active_users
            """)
            
            active_users_result = db.session.execute(active_users_query, {'yesterday': yesterday}).fetchone()
            real_time_stats['current_active_users'] = active_users_result.active_users or 0
            
            return jsonify({
                'success': True,
                'data': real_time_stats,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error in real-time statistics: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/analytics/export', methods=['GET'])
    def export_analytics_data():
        """
        Export analytics data in JSON format for external analysis
        """
        try:
            # Verify JWT authentication manually
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            export_type = request.args.get('type', 'full')  # 'full', 'user', 'platform'
            
            # Convert string user_id back to int for database query
            current_user_id_int = int(current_user_id)
            
            if export_type == 'user':
                data = analytics_manager.get_user_activity_history(current_user_id_int)
            elif export_type == 'platform':
                data = analytics_manager.get_platform_usage_statistics()
            else:  # full export
                data = analytics_manager.get_comprehensive_dashboard_data(current_user_id_int)
            
            return jsonify({
                'success': True,
                'export_type': export_type,
                'export_timestamp': datetime.now().isoformat(),
                'data': data
            })
            
        except Exception as e:
            logger.error(f"Error in analytics export: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
