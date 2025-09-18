#!/usr/bin/env python3
"""
Migration: Update social_media_connections exclusivity constraints
- Drop global unique constraint (unique_platform_account) if it exists
- Create partial unique indexes to enforce exclusivity ONLY for Facebook and Instagram
  (unique per (platform, platform_user_id) where is_active = true)

Safe to run multiple times.
"""
import os
import sys
from dotenv import load_dotenv
import psycopg2

load_dotenv()

# Allow imports relative to this file if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_migration():
    db_url = os.getenv('DATABASE_URL', 'postgresql://username:password@localhost/socialmanager')

    # Naive parser for common postgres URL formats
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
            host = 'localhost'
            port = 5432
            database = db_url.split('/')[-1] if '/' in db_url else 'postgres'
            username = 'postgres'
            password = ''
    else:
        print('Unsupported DATABASE_URL format')
        return False

    conn = None
    try:
        conn = psycopg2.connect(host=host, port=port, database=database, user=username, password=password)
        conn.autocommit = False
        cur = conn.cursor()

        # 1) Drop the old unique constraint if it exists
        print('Dropping old unique constraint if exists...')
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE table_name = 'social_media_connections'
                      AND constraint_name = 'unique_platform_account'
                ) THEN
                    ALTER TABLE social_media_connections DROP CONSTRAINT unique_platform_account;
                END IF;
            END$$;
        """)

        # 2) Drop any previous partial unique indexes we might have created to avoid duplicates
        print('Dropping existing partial unique indexes if exist...')
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'ux_smc_fb_active'
                ) THEN
                    DROP INDEX ux_smc_fb_active;
                END IF;
                IF EXISTS (
                    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'ux_smc_ig_active'
                ) THEN
                    DROP INDEX ux_smc_ig_active;
                END IF;
            END$$;
        """)

        # 3) Create partial unique indexes for Facebook and Instagram only
        print('Creating partial unique indexes for Facebook and Instagram...')
        cur.execute("""
            CREATE UNIQUE INDEX ux_smc_fb_active
            ON social_media_connections (platform_user_id)
            WHERE platform = 'facebook' AND is_active = TRUE;
        """)
        cur.execute("""
            CREATE UNIQUE INDEX ux_smc_ig_active
            ON social_media_connections (platform_user_id)
            WHERE platform = 'instagram' AND is_active = TRUE;
        """)

        conn.commit()
        print('✅ Migration completed successfully.')
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        print('❌ Migration failed:', e)
        return False
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass

if __name__ == '__main__':
    run_migration()
