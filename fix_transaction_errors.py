#!/usr/bin/env python3
"""
Fix PostgreSQL transaction errors by clearing transaction state and implementing robust error handling
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_database_transactions():
    """Fix database transaction issues"""
    try:
        from models import db
        from flaskapp import app
        
        with app.app_context():
            print("🔧 Fixing database transaction state...")
            
            # Force rollback any existing transaction
            try:
                db.session.rollback()
                print("✅ Rolled back any existing transaction")
            except Exception as e:
                print(f"ℹ️  No active transaction to rollback: {e}")
            
            # Close any existing connections
            try:
                db.session.close()
                print("✅ Closed database session")
            except Exception as e:
                print(f"ℹ️  Session close info: {e}")
            
            # Test a simple query to ensure database is working
            try:
                from models import User
                user_count = User.query.count()
                print(f"✅ Database connection test successful - {user_count} users in database")
            except Exception as e:
                print(f"❌ Database connection test failed: {e}")
                return False
            
            print("🎉 Database transaction state fixed!")
            return True
            
    except Exception as e:
        print(f"❌ Error fixing database transactions: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_connection_creation():
    """Test connection creation with proper transaction handling"""
    try:
        from models import db, SocialMediaConnection
        from flaskapp import app
        from connection_service import ConnectionService
        
        with app.app_context():
            print("\n🧪 Testing connection creation...")
            
            # Clear any existing test connections
            try:
                test_connections = SocialMediaConnection.query.filter_by(
                    platform_user_id='test_transaction_fix'
                ).all()
                for conn in test_connections:
                    db.session.delete(conn)
                db.session.commit()
                print("✅ Cleared any existing test connections")
            except Exception as e:
                print(f"ℹ️  No test connections to clear: {e}")
                db.session.rollback()
            
            # Test creating a connection
            result = ConnectionService.create_connection(
                user_id=1,
                platform='reddit',
                platform_user_id='test_transaction_fix',
                platform_username='test_user'
            )
            
            print(f"Connection creation result: {result}")
            
            if result['success']:
                print("✅ Connection creation test successful!")
                
                # Clean up test connection
                try:
                    test_conn = SocialMediaConnection.query.filter_by(
                        platform_user_id='test_transaction_fix'
                    ).first()
                    if test_conn:
                        db.session.delete(test_conn)
                        db.session.commit()
                        print("✅ Cleaned up test connection")
                except Exception as e:
                    print(f"ℹ️  Cleanup info: {e}")
                
                return True
            else:
                print(f"❌ Connection creation failed: {result}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing connection creation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting database transaction fix...")
    
    # Step 1: Fix transaction state
    if fix_database_transactions():
        print("\n" + "="*50)
        
        # Step 2: Test connection creation
        if test_connection_creation():
            print("\n🎉 All tests passed! Database transactions are working correctly.")
            print("\n✅ You can now try connecting to social media platforms again.")
        else:
            print("\n❌ Connection creation test failed. Please check the logs above.")
    else:
        print("\n❌ Failed to fix database transaction state. Please check the logs above.")
