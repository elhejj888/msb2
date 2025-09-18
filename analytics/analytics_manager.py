import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import text, func, desc, asc
from collections import defaultdict
import json
from typing import Dict, List, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyticsManager:
    """
    Advanced Analytics Manager for Social Media Data Analysis
    Implements big data analysis techniques for comprehensive insights
    """
    
    def __init__(self, db):
        self.db = db
        self.platforms = ['instagram', 'facebook', 'x', 'reddit', 'pinterest', 'youtube']
        self.table_mapping = {
            'instagram': 'instagram_posts',
            'facebook': 'facebook_posts',
            'x': 'x_posts',
            'reddit': 'reddit_posts',
            'pinterest': 'pinterest_posts',
            'youtube': 'youtube_posts'
        }
        
    def get_platform_usage_statistics(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Analyze platform usage statistics with advanced metrics
        Returns comprehensive platform usage data for visualization
        """
        try:
            platform_stats = {}
            total_posts = 0
            
            # Get detailed statistics for each platform
            for platform in self.platforms:
                table_name = self.table_mapping[platform]
                
                # Execute raw SQL for better performance with large datasets
                where_clause = ""
                params = {}
                if start_date and end_date:
                    where_clause = "WHERE created_at >= :start_date AND created_at <= :end_date"
                    params = {"start_date": start_date, "end_date": end_date}
                query = text(f"""
                    SELECT 
                        COUNT(*) as total_posts,
                        COUNT(DISTINCT user_id) as unique_users,
                        AVG(CASE WHEN status = 'posted' THEN 1 ELSE 0 END) * 100 as success_rate,
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as posts_last_7_days,
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as posts_last_30_days,
                        MIN(created_at) as first_post_date,
                        MAX(created_at) as last_post_date
                    FROM {table_name}
                    {where_clause}
                """)
                
                result = self.db.session.execute(query, params).fetchone()
                
                if result:
                    # Convert database results to appropriate types to avoid Decimal issues
                    platform_data = {
                        'platform': platform,
                        'total_posts': int(result.total_posts or 0),
                        'unique_users': int(result.unique_users or 0),
                        'success_rate': round(float(result.success_rate or 0), 2),
                        'posts_last_7_days': int(result.posts_last_7_days or 0),
                        'posts_last_30_days': int(result.posts_last_30_days or 0),
                        'first_post_date': result.first_post_date.isoformat() if result.first_post_date else None,
                        'last_post_date': result.last_post_date.isoformat() if result.last_post_date else None,
                        'activity_score': self._calculate_activity_score(result)
                    }
                    
                    platform_stats[platform] = platform_data
                    total_posts += platform_data['total_posts']
            
            # Calculate percentages and rankings
            for platform in platform_stats:
                if total_posts > 0:
                    platform_stats[platform]['usage_percentage'] = round(
                        (platform_stats[platform]['total_posts'] / total_posts) * 100, 2
                    )
                else:
                    platform_stats[platform]['usage_percentage'] = 0
            
            # Sort platforms by usage
            sorted_platforms = sorted(
                platform_stats.items(), 
                key=lambda x: x[1]['total_posts'], 
                reverse=True
            )
            
            return {
                'platform_statistics': platform_stats,
                'total_posts_across_platforms': total_posts,
                'most_used_platform': sorted_platforms[0][0] if sorted_platforms else None,
                'platform_rankings': [{'platform': p[0], 'posts': p[1]['total_posts']} for p in sorted_platforms],
                'analysis_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in platform usage statistics: {str(e)}")
            return {'error': str(e)}
    
    def get_user_engagement_metrics(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive user engagement metrics
        """
        try:
            # Get total registered users
            total_users_query = text("SELECT COUNT(*) as total FROM users WHERE is_active = true")
            total_users = int(self.db.session.execute(total_users_query).fetchone().total)
            
            # Get active users (users who have posted)
            date_filter = ""
            params = {}
            if start_date and end_date:
                date_filter = "WHERE created_at >= :start_date AND created_at <= :end_date"
                params = {"start_date": start_date, "end_date": end_date}
            active_users_query = text(f"""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM (
                    SELECT user_id FROM instagram_posts {date_filter}
                    UNION
                    SELECT user_id FROM facebook_posts {date_filter}
                    UNION
                    SELECT user_id FROM x_posts {date_filter}
                    UNION
                    SELECT user_id FROM reddit_posts {date_filter}
                    UNION
                    SELECT user_id FROM pinterest_posts {date_filter}
                    UNION
                    SELECT user_id FROM youtube_posts {date_filter}
                ) as all_users
            """)
            active_users = int(self.db.session.execute(active_users_query, params).fetchone().active_users or 0)
            
            # Get user activity distribution
            user_activity_query = text(f"""
                SELECT 
                    user_id,
                    COUNT(*) as total_posts,
                    COUNT(DISTINCT platform) as platforms_used
                FROM (
                    SELECT user_id, 'instagram' as platform FROM instagram_posts {date_filter}
                    UNION ALL
                    SELECT user_id, 'facebook' as platform FROM facebook_posts {date_filter}
                    UNION ALL
                    SELECT user_id, 'x' as platform FROM x_posts {date_filter}
                    UNION ALL
                    SELECT user_id, 'reddit' as platform FROM reddit_posts {date_filter}
                    UNION ALL
                    SELECT user_id, 'pinterest' as platform FROM pinterest_posts {date_filter}
                    UNION ALL
                    SELECT user_id, 'youtube' as platform FROM youtube_posts {date_filter}
                ) as all_posts
                GROUP BY user_id
                ORDER BY total_posts DESC
            """)
            
            user_activity_results = self.db.session.execute(user_activity_query, params).fetchall()
            
            # Calculate engagement metrics
            engagement_levels = {
                'high_engagement': 0,  # 10+ posts
                'medium_engagement': 0,  # 3-9 posts
                'low_engagement': 0,  # 1-2 posts
                'inactive': total_users - active_users
            }
            
            multi_platform_users = 0
            total_posts_by_active_users = 0
            
            for user in user_activity_results:
                # Convert database results to int to avoid type issues
                user_total_posts = int(user.total_posts or 0)
                user_platforms_used = int(user.platforms_used or 0)
                
                total_posts_by_active_users += user_total_posts
                
                if user_platforms_used > 1:
                    multi_platform_users += 1
                
                if user_total_posts >= 10:
                    engagement_levels['high_engagement'] += 1
                elif user_total_posts >= 3:
                    engagement_levels['medium_engagement'] += 1
                else:
                    engagement_levels['low_engagement'] += 1
            
            # Calculate averages
            avg_posts_per_active_user = (
                total_posts_by_active_users / active_users if active_users > 0 else 0
            )
            
            return {
                'total_registered_users': total_users,
                'active_users': active_users,
                'inactive_users': total_users - active_users,
                'activation_rate': round((active_users / total_users) * 100, 2) if total_users > 0 else 0,
                'multi_platform_users': multi_platform_users,
                'multi_platform_rate': round((multi_platform_users / active_users) * 100, 2) if active_users > 0 else 0,
                'engagement_levels': engagement_levels,
                'avg_posts_per_active_user': round(avg_posts_per_active_user, 2),
                'top_users': [
                    {
                        'user_id': int(user.user_id),
                        'total_posts': int(user.total_posts or 0),
                        'platforms_used': int(user.platforms_used or 0)
                    } for user in user_activity_results[:10]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in user engagement metrics: {str(e)}")
            return {'error': str(e)}
    
    def get_temporal_trends(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze temporal trends and patterns in social media usage
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Daily activity trends for each platform
            daily_trends = {}
            
            for platform in self.platforms:
                table_name = self.table_mapping[platform]
                
                query = text(f"""
                    SELECT 
                        DATE(created_at) as post_date,
                        COUNT(*) as posts_count,
                        COUNT(DISTINCT user_id) as unique_users
                    FROM {table_name}
                    WHERE created_at >= :start_date AND created_at <= :end_date
                    GROUP BY DATE(created_at)
                    ORDER BY post_date
                """)
                
                results = self.db.session.execute(
                    query, 
                    {'start_date': start_date, 'end_date': end_date}
                ).fetchall()
                
                daily_trends[platform] = [
                    {
                        'date': result.post_date.isoformat(),
                        'posts': int(result.posts_count or 0),
                        'users': int(result.unique_users or 0)
                    } for result in results
                ]
            
            # Weekly patterns (day of week analysis)
            weekly_patterns = self._analyze_weekly_patterns(start_date, end_date)
            
            # Hourly patterns
            hourly_patterns = self._analyze_hourly_patterns(start_date, end_date)
            
            return {
                'daily_trends': daily_trends,
                'weekly_patterns': weekly_patterns,
                'hourly_patterns': hourly_patterns,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                }
            }
            
        except Exception as e:
            logger.error(f"Error in temporal trends analysis: {str(e)}")
            return {'error': str(e)}
    
    def get_user_activity_history(self, user_id: int) -> Dict[str, Any]:
        """
        Get detailed activity history for a specific user across all platforms
        """
        try:
            user_activity = {}
            total_posts = 0
            
            for platform in self.platforms:
                table_name = self.table_mapping[platform]
                
                query = text(f"""
                    SELECT 
                        id,
                        created_at,
                        status,
                        error_message,
                        {self._get_platform_specific_fields(platform)}
                    FROM {table_name}
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT 50
                """)
                
                results = self.db.session.execute(query, {'user_id': user_id}).fetchall()
                
                platform_posts = []
                for result in results:
                    post_data = {
                        'id': result.id,
                        'created_at': result.created_at.isoformat(),
                        'status': result.status,
                        'error_message': result.error_message
                    }
                    
                    # Add platform-specific data
                    post_data.update(self._extract_platform_specific_data(platform, result))
                    platform_posts.append(post_data)
                
                user_activity[platform] = {
                    'posts': platform_posts,
                    'total_posts': len(platform_posts),
                    'success_rate': self._calculate_success_rate(platform_posts)
                }
                
                total_posts += len(platform_posts)
            
            # Calculate user statistics
            user_stats = self._calculate_user_statistics(user_id, user_activity)
            
            return {
                'user_id': user_id,
                'platform_activity': user_activity,
                'user_statistics': user_stats,
                'total_posts_across_platforms': total_posts
            }
            
        except Exception as e:
            logger.error(f"Error in user activity history: {str(e)}")
            return {'error': str(e)}
    
    def get_content_analysis(self) -> Dict[str, Any]:
        """
        Analyze content patterns and characteristics across platforms
        """
        try:
            content_analysis = {}
            
            # Analyze content length patterns
            for platform in self.platforms:
                table_name = self.table_mapping[platform]
                content_field = self._get_content_field(platform)
                
                if content_field:
                    query = text(f"""
                        SELECT 
                            AVG(LENGTH({content_field})) as avg_length,
                            MIN(LENGTH({content_field})) as min_length,
                            MAX(LENGTH({content_field})) as max_length,
                            COUNT(*) as total_posts
                        FROM {table_name}
                        WHERE {content_field} IS NOT NULL AND {content_field} != ''
                    """)
                    
                    result = self.db.session.execute(query).fetchone()
                    
                    content_analysis[platform] = {
                        'avg_content_length': round(float(result.avg_length or 0), 2),
                        'min_content_length': int(result.min_length or 0),
                        'max_content_length': int(result.max_length or 0),
                        'total_posts_with_content': int(result.total_posts or 0)
                    }
            
            return {
                'content_analysis': content_analysis,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in content analysis: {str(e)}")
            return {'error': str(e)}

    def get_comprehensive_dashboard_data(self, user_id: Optional[int] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get all analytics data for the dashboard in a single call
        Optional start_date and end_date filter platform and user metrics.
        """
        try:
            # Fallback days window when only days-based method is available
            days_window = 30 if not (start_date and end_date) else max(1, (end_date - start_date).days)
            dashboard_data = {
                'platform_usage': self.get_platform_usage_statistics(start_date, end_date),
                'user_engagement': self.get_user_engagement_metrics(start_date, end_date),
                'temporal_trends': self.get_temporal_trends(days_window),
                'content_analysis': self.get_content_analysis()
            }
            
            if user_id is not None:
                dashboard_data['user_activity'] = self.get_user_activity_history(user_id)
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error in comprehensive dashboard data: {str(e)}")
            return {'error': str(e)}

    # NOTE: Keep original signature used by routes
    def get_user_activity_history(self, user_id: int) -> Dict[str, Any]:
        """
        Get detailed activity history for a specific user across all platforms
        """
        try:
            user_activity = {}
            total_posts = 0
            
            for platform in self.platforms:
                table_name = self.table_mapping[platform]
                
                query = text(f"""
                    SELECT 
                        id,
                        created_at,
                        status,
                        error_message,
                        {self._get_platform_specific_fields(platform)}
                    FROM {table_name}
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT 50
                """)
                
                results = self.db.session.execute(query, {'user_id': user_id}).fetchall()
                
                platform_posts = []
                for result in results:
                    post_data = {
                        'id': result.id,
                        'created_at': result.created_at.isoformat(),
                        'status': result.status,
                        'error_message': result.error_message
                    }
                    
                    # Add platform-specific data
                    post_data.update(self._extract_platform_specific_data(platform, result))
                    platform_posts.append(post_data)
                
                user_activity[platform] = {
                    'posts': platform_posts,
                    'total_posts': len(platform_posts),
                    'success_rate': self._calculate_success_rate(platform_posts)
                }
                
                total_posts += len(platform_posts)
            
            # Calculate user statistics
            user_stats = self._calculate_user_statistics(user_id, user_activity)
            
            return {
                'user_id': user_id,
                'platform_activity': user_activity,
                'user_statistics': user_stats,
                'total_posts_across_platforms': total_posts
            }
            
        except Exception as e:
            logger.error(f"Error in user activity history: {str(e)}")
            return {'error': str(e)}
    
    def get_predictions(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate simple predictive insights for admin dashboard.
        - Best platforms: based on recent success_rate and activity_score
        - Best posting hours: based on historical hourly patterns
        - Top content topics: naive keyword frequency across content fields
        """
        try:
            # Use existing analyses
            platform_usage = self.get_platform_usage_statistics(start_date, end_date)
            temporal = self.get_temporal_trends(days=30 if not (start_date and end_date) else (end_date - start_date).days)

            # Best platforms by combined score
            rankings = []
            for p, s in platform_usage.get('platform_statistics', {}).items():
                score = float(s.get('activity_score', 0)) + float(s.get('success_rate', 0)) / 5.0
                rankings.append({
                    'platform': p,
                    'score': round(score, 2),
                    'success_rate': s.get('success_rate', 0),
                    'total_posts': s.get('total_posts', 0)
                })
            best_platforms = sorted(rankings, key=lambda x: x['score'], reverse=True)

            # Best posting hours by total posts across platforms
            hour_counts: Dict[int, int] = defaultdict(int)
            for p, hours in temporal.get('hourly_patterns', {}).items():
                for hour, count in hours.items():
                    hour_counts[int(hour)] += int(count)
            best_hours = sorted([
                {'hour': h, 'posts': c} for h, c in hour_counts.items()
            ], key=lambda x: x['posts'], reverse=True)[:5]

            # Naive topic extraction via keyword frequency
            keywords: Dict[str, int] = defaultdict(int)
            for platform in self.platforms:
                table = self.table_mapping[platform]
                content_field = self._get_content_field(platform)
                if not content_field:
                    continue
                where_clause = ""
                params = {}
                if start_date and end_date:
                    where_clause = "WHERE created_at >= :start_date AND created_at <= :end_date AND "
                    params = {"start_date": start_date, "end_date": end_date}
                else:
                    where_clause = "WHERE "
                query = text(f"""
                    SELECT {content_field} as content
                    FROM {table}
                    {where_clause}{content_field} IS NOT NULL AND {content_field} != ''
                    LIMIT 200
                """)
                results = self.db.session.execute(query, params).fetchall()
                for row in results:
                    text_content = (row.content or '').lower()
                    for token in [t.strip("#.,!?\n\r\t ") for t in text_content.split()]:
                        if len(token) < 3:
                            continue
                        if token in {"the","and","for","with","this","that","http","https","www","you","your","have","from","are"}:
                            continue
                        keywords[token] += 1

            top_topics = sorted([
                {'term': k, 'count': v} for k, v in keywords.items()
            ], key=lambda x: x['count'], reverse=True)[:15]

            return {
                'best_platforms': best_platforms,
                'best_posting_hours': best_hours,
                'top_content_topics': top_topics,
                'analysis_period': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            logger.error(f"Error generating predictions: {str(e)}")
            return {'error': str(e)}
    
    # Helper methods
    def _calculate_activity_score(self, result) -> float:
        """Calculate activity score based on various metrics"""
        # Convert all database results to float to avoid Decimal type issues
        total_posts = float(result.total_posts or 0)
        unique_users = float(result.unique_users or 0)
        success_rate = float(result.success_rate or 0)
        posts_last_7_days = float(result.posts_last_7_days or 0)
        
        posts_score = min(total_posts / 100, 1.0) * 40
        users_score = min(unique_users / 50, 1.0) * 30
        success_score = success_rate / 100 * 20
        recent_score = min(posts_last_7_days / 10, 1.0) * 10
        
        return round(posts_score + users_score + success_score + recent_score, 2)
    
    def _analyze_weekly_patterns(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze weekly posting patterns"""
        try:
            weekly_data = {}
            
            for platform in self.platforms:
                table_name = self.table_mapping[platform]
                
                query = text(f"""
                    SELECT 
                        EXTRACT(DOW FROM created_at) as day_of_week,
                        COUNT(*) as posts_count
                    FROM {table_name}
                    WHERE created_at >= :start_date AND created_at <= :end_date
                    GROUP BY EXTRACT(DOW FROM created_at)
                    ORDER BY day_of_week
                """)
                
                results = self.db.session.execute(
                    query, 
                    {'start_date': start_date, 'end_date': end_date}
                ).fetchall()
                
                weekly_data[platform] = {
                    int(result.day_of_week): int(result.posts_count or 0) 
                    for result in results
                }
        
            return weekly_data
        
        except Exception as e:
            logger.error(f"Error in weekly patterns analysis: {str(e)}")
            return {}
    
    def _analyze_hourly_patterns(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze hourly posting patterns"""
        try:
            hourly_data = {}
            
            for platform in self.platforms:
                table_name = self.table_mapping[platform]
                
                query = text(f"""
                    SELECT 
                        EXTRACT(HOUR FROM created_at) as hour_of_day,
                        COUNT(*) as posts_count
                    FROM {table_name}
                    WHERE created_at >= :start_date AND created_at <= :end_date
                    GROUP BY EXTRACT(HOUR FROM created_at)
                    ORDER BY hour_of_day
                """)
                
                results = self.db.session.execute(
                    query, 
                    {'start_date': start_date, 'end_date': end_date}
                ).fetchall()
                
                hourly_data[platform] = {
                    int(result.hour_of_day): int(result.posts_count or 0) 
                    for result in results
                }
            
            return hourly_data
            
        except Exception as e:
            logger.error(f"Error in hourly patterns analysis: {str(e)}")
            return {}
    
    def _get_platform_specific_fields(self, platform: str) -> str:
        """Get platform-specific fields for queries"""
        field_mapping = {
            'instagram': 'caption, media_type',
            'facebook': 'message, link, scheduled_time',
            'x': 'text, reply_to_tweet_id',
            'reddit': 'subreddit_name, title, content, is_spoiler, nsfw',
            'pinterest': 'board_id, title, description, link',
            'youtube': 'title, description, link, privacy_status, video_id, video_url, view_count, like_count, comment_count'
        }
        return field_mapping.get(platform, '')
    
    def _extract_platform_specific_data(self, platform: str, result) -> Dict[str, Any]:
        """Extract platform-specific data from query result"""
        try:
            if platform == 'instagram':
                return {
                    'caption': getattr(result, 'caption', None),
                    'media_type': getattr(result, 'media_type', None)
                }
            elif platform == 'facebook':
                return {
                    'message': getattr(result, 'message', None),
                    'link': getattr(result, 'link', None),
                    'scheduled_time': getattr(result, 'scheduled_time', None)
                }
            elif platform == 'x':
                return {
                    'text': getattr(result, 'text', None),
                    'reply_to_tweet_id': getattr(result, 'reply_to_tweet_id', None)
                }
            elif platform == 'reddit':
                return {
                    'subreddit_name': getattr(result, 'subreddit_name', None),
                    'title': getattr(result, 'title', None),
                    'content': getattr(result, 'content', None),
                    'is_spoiler': getattr(result, 'is_spoiler', None),
                    'nsfw': getattr(result, 'nsfw', None)
                }
            elif platform == 'pinterest':
                return {
                    'board_id': getattr(result, 'board_id', None),
                    'title': getattr(result, 'title', None),
                    'description': getattr(result, 'description', None),
                    'link': getattr(result, 'link', None)
                }
            elif platform == 'youtube':
                return {
                    'title': getattr(result, 'title', None),
                    'description': getattr(result, 'description', None),
                    'link': getattr(result, 'link', None),
                    'privacy_status': getattr(result, 'privacy_status', None),
                    'video_id': getattr(result, 'video_id', None),
                    'video_url': getattr(result, 'video_url', None),
                    'view_count': getattr(result, 'view_count', None),
                    'like_count': getattr(result, 'like_count', None),
                    'comment_count': getattr(result, 'comment_count', None)
                }
            return {}
        except Exception as e:
            logger.error(f"Error extracting platform data for {platform}: {str(e)}")
            return {}
    
    def _get_content_field(self, platform: str) -> str:
        """Get the main content field for each platform"""
        content_fields = {
            'instagram': 'caption',
            'facebook': 'message',
            'x': 'text',
            'reddit': 'content',
            'pinterest': 'description',
            'youtube': 'description'
        }
        return content_fields.get(platform)
    
    def _calculate_success_rate(self, posts: List[Dict]) -> float:
        """Calculate success rate for posts"""
        if not posts:
            return 0.0
        
        successful_posts = sum(1 for post in posts if post.get('status') == 'posted')
        return round((successful_posts / len(posts)) * 100, 2)
    
    def _calculate_user_statistics(self, user_id: int, user_activity: Dict) -> Dict[str, Any]:
        """Calculate comprehensive user statistics"""
        try:
            total_posts = sum(activity['total_posts'] for activity in user_activity.values())
            platforms_used = sum(1 for activity in user_activity.values() if activity['total_posts'] > 0)
            
            avg_success_rate = np.mean([
                activity['success_rate'] for activity in user_activity.values() 
                if activity['total_posts'] > 0
            ]) if platforms_used > 0 else 0
            
            # Get user registration date
            user_query = text("SELECT date_created FROM users WHERE id = :user_id")
            user_result = self.db.session.execute(user_query, {'user_id': user_id}).fetchone()
            
            registration_date = user_result.date_created if user_result else None
            
            return {
                'total_posts': total_posts,
                'platforms_used': platforms_used,
                'avg_success_rate': round(avg_success_rate, 2),
                'most_active_platform': max(
                    user_activity.items(), 
                    key=lambda x: x[1]['total_posts']
                )[0] if total_posts > 0 else None,
                'registration_date': registration_date.isoformat() if registration_date else None,
                'user_engagement_level': self._classify_user_engagement(total_posts, platforms_used)
            }
            
        except Exception as e:
            logger.error(f"Error calculating user statistics: {str(e)}")
            return {}
    
    def _classify_user_engagement(self, total_posts: int, platforms_used: int) -> str:
        """Classify user engagement level"""
        if total_posts >= 20 and platforms_used >= 3:
            return 'High'
        elif total_posts >= 10 or platforms_used >= 2:
            return 'Medium'
        elif total_posts >= 1:
            return 'Low'
        else:
            return 'Inactive'
