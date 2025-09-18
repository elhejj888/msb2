from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def setup_admin_routes(app, db):
    """Register admin-only analytics routes with RBAC checks"""

    def admin_required():
        """Simple RBAC check: only allow users with role == 'admin'"""
        # Verify JWT
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        try:
            from models import User
            user = User.query.get(int(user_id))
            if not user or user.role != 'admin':
                return False, jsonify({'success': False, 'error': 'Admin access required'}), 403
            return True, user, None
        except Exception as e:
            logger.error(f"RBAC check error: {str(e)}")
            return False, jsonify({'success': False, 'error': 'Authorization error'}), 500

    @app.route('/api/admin/stats/users-count', methods=['GET'])
    def admin_users_count():
        ok, payload, status = admin_required()
        if not ok:
            return payload, status
        try:
            result = db.session.execute(text('SELECT COUNT(*) as cnt FROM users')).fetchone()
            total_users = int(result.cnt or 0)
            return jsonify({'success': True, 'data': {'total_users': total_users}})
        except Exception as e:
            logger.error(f"Admin users-count error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/admin/stats/posts-per-platform', methods=['GET'])
    def admin_posts_per_platform():
        ok, payload, status = admin_required()
        if not ok:
            return payload, status
        try:
            # Aggregate counts across all platforms
            queries = {
                'instagram': 'SELECT COUNT(*) FROM instagram_posts',
                'tiktok': 'SELECT COUNT(*) FROM tiktok_posts',
                'facebook': 'SELECT COUNT(*) FROM facebook_posts',
                'x': 'SELECT COUNT(*) FROM x_posts',
                'reddit': 'SELECT COUNT(*) FROM reddit_posts',
                'pinterest': 'SELECT COUNT(*) FROM pinterest_posts',
                'youtube': 'SELECT COUNT(*) FROM youtube_posts'
            }
            data = {}
            for platform, q in queries.items():
                try:
                    res = db.session.execute(text(q)).fetchone()
                    data[platform] = int((res[0] if res else 0) or 0)
                except Exception:
                    # Table might not exist in some deployments; default to 0
                    data[platform] = 0
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            logger.error(f"Admin posts-per-platform error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/admin/stats/best-platform', methods=['GET'])
    def admin_best_platform():
        ok, payload, status = admin_required()
        if not ok:
            return payload, status
        try:
            # Use AnalyticsManager to compute best platform by interaction
            try:
                from analytics.analytics_manager import AnalyticsManager
                analytics_manager = AnalyticsManager(db)
                stats = analytics_manager.get_platform_usage_statistics()
                best = stats.get('most_used_platform')
                rankings = stats.get('platform_rankings', [])
                return jsonify({'success': True, 'data': {'best_platform': best, 'rankings': rankings}})
            except Exception as e2:
                logger.warning(f"Falling back to counts-only best-platform due to: {str(e2)}")
                # Fallback to count-based best platform
                ok_resp, data_resp = admin_posts_per_platform()
                if isinstance(ok_resp, tuple):
                    # Error from above
                    return ok_resp
                counts = data_resp.get_json().get('data', {})
                best = max(counts.items(), key=lambda x: x[1])[0] if counts else None
                rankings = sorted(
                    [{'platform': k, 'posts': v} for k, v in counts.items()],
                    key=lambda x: x['posts'], reverse=True
                )
                return jsonify({'success': True, 'data': {'best_platform': best, 'rankings': rankings}})
        except Exception as e:
            logger.error(f"Admin best-platform error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
