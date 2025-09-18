#!/usr/bin/env python3
"""
Database migration script to add missing additional_data column to social_media_connections table
"""

import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def add_additional_data_column():
    """Add the missing additional_data column to social_media_connections table"""
    
    # Database connection parameters from environment
    db_url = os.getenv('DATABASE_URL', 'postgresql://username:password@localhost/socialmanager')
    
    # Parse the database URL to get connection parameters
    # Format: postgresql://username:password@host:port/database
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', '')
        if '@' in db_url:
            auth_part, host_part = db_url.split('@', 1)
            if ':' in auth_part:
                username, password = auth_part.split(':', 1)
            else:
                username = auth_part
                password = ''
            
            if '/' in host_part:
                host_port, database = host_part.split('/', 1)
                if ':' in host_port:
                    host, port = host_port.split(':', 1)
                    port = int(port)
                else:
                    host = host_port
                    port = 5432
            else:
                host = host_part
                port = 5432
                database = 'postgres'
        else:
            # No auth part, assume localhost
            host = 'localhost'
            port = 5432
            database = db_url.split('/')[-1] if '/' in db_url else 'postgres'
            username = 'postgres'
            password = ''
    else:
        print("Unsupported database URL format")
        return False
    
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password
        )
        
        cursor = conn.cursor()
        
        # Check if the column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'social_media_connections' 
            AND column_name = 'additional_data'
        """)
        
        if cursor.fetchone():
            print("Column 'additional_data' already exists in social_media_connections table")
            cursor.close()
            conn.close()
            return True
        
        # Add the missing column
        print("Adding 'additional_data' column to social_media_connections table...")
        cursor.execute("""
            ALTER TABLE social_media_connections 
            ADD COLUMN additional_data TEXT
        """)
        
        # Commit the changes
        conn.commit()
        print("Successfully added 'additional_data' column!")
        
        # Verify the column was added
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'social_media_connections' 
            AND column_name = 'additional_data'
        """)
        
        if cursor.fetchone():
            print("Verification: Column 'additional_data' now exists in the table")
            success = True
        else:
            print("Error: Column was not added successfully")
            success = False
        
        cursor.close()
        conn.close()
        return success
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Starting database migration...")
    print("Adding missing 'additional_data' column to social_media_connections table")
    
    if add_additional_data_column():
        print("\n✅ Migration completed successfully!")
        print("The social_media_connections table now has the additional_data column.")
        print("You can now restart your Flask application.")
    else:
        print("\n❌ Migration failed!")
        print("Please check the error messages above and try again.")
