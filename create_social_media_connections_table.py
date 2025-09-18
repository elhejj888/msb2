"""
Database migration script to create social_media_connections table
Run this script to add the new table for account exclusivity enforcement
"""

from flaskapp import app
from models import db, SocialMediaConnection

def create_social_media_connections_table():
    """Create the social_media_connections table"""
    with app.app_context():
        try:
            # Create the table
            db.create_all()
            print("✅ Successfully created social_media_connections table")
            
            # Verify table was created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'social_media_connections' in tables:
                print("✅ Table 'social_media_connections' confirmed in database")
                
                # Show table structure
                columns = inspector.get_columns('social_media_connections')
                print("\n📋 Table structure:")
                for column in columns:
                    print(f"  - {column['name']}: {column['type']}")
                
                # Show constraints
                constraints = inspector.get_unique_constraints('social_media_connections')
                if constraints:
                    print("\n🔒 Unique constraints:")
                    for constraint in constraints:
                        print(f"  - {constraint['name']}: {constraint['column_names']}")
                
            else:
                print("❌ Table 'social_media_connections' not found in database")
                
        except Exception as e:
            print(f"❌ Error creating table: {e}")

if __name__ == "__main__":
    print("🚀 Creating social_media_connections table...")
    create_social_media_connections_table()
    print("✨ Migration completed!")
