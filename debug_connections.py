#!/usr/bin/env python3
"""
Debug script to check social media connections in database
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import db, SocialMediaConnection, User
from flaskapp import app

def debug_connections():
    """Debug all connections in the database"""
    with app.app_context():
        try:
            # Get all connections
            connections = SocialMediaConnection.query.all()
            print(f"Total connections in database: {len(connections)}")
            print("-" * 80)
            
            if not connections:
                print("No connections found in database")
                return
            
            for conn in connections:
                print(f"Connection ID: {conn.id}")
                print(f"  User ID: {conn.user_id}")
                print(f"  Platform: {conn.platform}")
                print(f"  Platform User ID: {conn.platform_user_id}")
                print(f"  Platform Username: {conn.platform_username}")
                print(f"  Active: {conn.is_active}")
                print(f"  Created: {conn.created_at}")
                print(f"  Updated: {conn.updated_at}")
                print("-" * 40)
            
            # Check for duplicate platform_user_ids
            print("\nChecking for potential duplicates:")
            platforms = ['reddit', 'x', 'pinterest', 'tiktok']
            for platform in platforms:
                platform_connections = SocialMediaConnection.query.filter_by(
                    platform=platform,
                    is_active=True
                ).all()
                
                if platform_connections:
                    print(f"\n{platform.upper()} active connections:")
                    for conn in platform_connections:
                        print(f"  User {conn.user_id}: {conn.platform_user_id} ({conn.platform_username})")
                else:
                    print(f"\n{platform.upper()}: No active connections")
                    
        except Exception as e:
            print(f"Error debugging connections: {e}")

def clear_all_connections():
    """Clear all connections (for testing)"""
    with app.app_context():
        try:
            count = SocialMediaConnection.query.count()
            SocialMediaConnection.query.delete()
            db.session.commit()
            print(f"Cleared {count} connections from database")
        except Exception as e:
            print(f"Error clearing connections: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_all_connections()
    else:
        debug_connections()
