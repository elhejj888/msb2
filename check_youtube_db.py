#!/usr/bin/env python3
"""
Check YouTube connections in database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from connection_service import ConnectionService
import psycopg2
from dotenv import load_dotenv

def check_youtube_connections():
    """Check all YouTube connections in database"""
    load_dotenv()
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'social_media_manager'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password'),
            port=os.getenv('DB_PORT', '5432')
        )
        
        cursor = conn.cursor()
        
        # Check all YouTube connections
        cursor.execute("""
            SELECT user_id, platform, platform_user_id, platform_username, 
                   created_at, updated_at, access_token IS NOT NULL as has_token
            FROM social_media_connections 
            WHERE platform = 'youtube'
            ORDER BY created_at DESC
        """)
        
        connections = cursor.fetchall()
        
        print("YouTube Connections in Database:")
        print("=" * 60)
        
        if connections:
            for conn_data in connections:
                user_id, platform, platform_user_id, platform_username, created_at, updated_at, has_token = conn_data
                print(f"User ID: {user_id}")
                print(f"Platform User ID: {platform_user_id}")
                print(f"Username: {platform_username}")
                print(f"Has Token: {has_token}")
                print(f"Created: {created_at}")
                print(f"Updated: {updated_at}")
                print("-" * 40)
        else:
            print("No YouTube connections found in database")
        
        cursor.close()
        conn.close()
        
        return len(connections)
        
    except Exception as e:
        print(f"Error checking database: {e}")
        return 0

def test_connection_service(user_id):
    """Test ConnectionService for specific user"""
    print(f"\nTesting ConnectionService for user {user_id}:")
    print("=" * 40)
    
    try:
        status = ConnectionService.get_user_connection_status(user_id, 'youtube')
        print(f"Connection status: {status}")
        return status
    except Exception as e:
        print(f"Error with ConnectionService: {e}")
        return None

if __name__ == "__main__":
    count = check_youtube_connections()
    print(f"\nTotal YouTube connections: {count}")
    
    # Test specific user
    test_connection_service(4)
