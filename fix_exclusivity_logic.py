#!/usr/bin/env python3
"""
Fix script to address account exclusivity logic issues across all platforms
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
from connection_service import ConnectionService

def test_exclusivity_logic():
    """Test the exclusivity logic with sample data"""
    with app.app_context():
        try:
            # Clear all existing connections first
            SocialMediaConnection.query.delete()
            db.session.commit()
            print("Cleared all existing connections")
            
            # Test 1: Check availability when no connections exist
            print("\n=== Test 1: Check availability when no connections exist ===")
            result = ConnectionService.check_account_availability('reddit', 'test_user_123')
            print(f"Result: {result}")
            print(f"Should be available: {result.get('available', False)}")
            
            # Test 2: Create a connection and check availability
            print("\n=== Test 2: Create connection and check availability ===")
            create_result = ConnectionService.create_connection(
                user_id=1,
                platform='reddit',
                platform_user_id='test_user_123',
                platform_username='test_user'
            )
            print(f"Create result: {create_result}")
            
            # Test 3: Check availability for same account (should be unavailable)
            print("\n=== Test 3: Check availability for same account ===")
            result = ConnectionService.check_account_availability('reddit', 'test_user_123')
            print(f"Result: {result}")
            print(f"Should be unavailable: {not result.get('available', True)}")
            
            # Test 4: Check availability for different account (should be available)
            print("\n=== Test 4: Check availability for different account ===")
            result = ConnectionService.check_account_availability('reddit', 'different_user_456')
            print(f"Result: {result}")
            print(f"Should be available: {result.get('available', False)}")
            
            # Test 5: Check availability for same user (should be available)
            print("\n=== Test 5: Check availability for same user (current_user_id=1) ===")
            result = ConnectionService.check_account_availability('reddit', 'test_user_123', current_user_id=1)
            print(f"Result: {result}")
            print(f"Should be available for same user: {result.get('available', False)}")
            
            # Clean up
            SocialMediaConnection.query.delete()
            db.session.commit()
            print("\nCleaned up test data")
            
        except Exception as e:
            print(f"Error in test: {e}")
            import traceback
            traceback.print_exc()

def debug_database_state():
    """Debug the current database state"""
    with app.app_context():
        try:
            connections = SocialMediaConnection.query.all()
            print(f"Total connections: {len(connections)}")
            
            for conn in connections:
                print(f"ID: {conn.id}, User: {conn.user_id}, Platform: {conn.platform}")
                print(f"  Platform User ID: '{conn.platform_user_id}'")
                print(f"  Username: '{conn.platform_username}'")
                print(f"  Active: {conn.is_active}")
                print(f"  Created: {conn.created_at}")
                print("-" * 40)
                
        except Exception as e:
            print(f"Error debugging database: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_exclusivity_logic()
    else:
        debug_database_state()
