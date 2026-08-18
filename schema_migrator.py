import os
import time
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DB_URL = os.getenv("SUPABASE_DB_URL")

MIGRATIONS = [
    (
        "001_initial_core_schema",
        """
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

        CREATE TABLE IF NOT EXISTS paired_devices (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            device_token VARCHAR(64) UNIQUE NOT NULL,
            device_name VARCHAR(100) NOT NULL,
            hardware_model VARCHAR(100),
            connection_mode VARCHAR(20) NOT NULL CHECK (connection_mode IN ('webusb', 'qr_wireless', 'daemon', 'adb')),
            sim_count SMALLINT NOT NULL DEFAULT 1,
            ip_address VARCHAR(45),
            last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
            status VARCHAR(20) NOT NULL DEFAULT 'ONLINE' CHECK (status IN ('ONLINE', 'OFFLINE', 'BUSY')),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_paired_devices_status ON paired_devices(status, last_heartbeat DESC);

        CREATE TABLE IF NOT EXISTS daily_sim_quotas (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            device_id UUID NOT NULL REFERENCES paired_devices(id) ON DELETE CASCADE,
            sim_slot SMALLINT NOT NULL DEFAULT 1 CHECK (sim_slot IN (1, 2)),
            carrier_name VARCHAR(50) NOT NULL,
            quota_date DATE NOT NULL DEFAULT CURRENT_DATE,
            sent_today INT NOT NULL DEFAULT 0,
            daily_limit INT NOT NULL DEFAULT 100,
            last_reset_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_device_sim_date UNIQUE(device_id, sim_slot, quota_date)
        );
        CREATE INDEX IF NOT EXISTS idx_daily_quotas_lookup ON daily_sim_quotas(device_id, quota_date);

        CREATE TABLE IF NOT EXISTS sms_campaigns (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            title VARCHAR(150) NOT NULL,
            target_source VARCHAR(30) NOT NULL CHECK (target_source IN ('manage_jobs', 'global_search', 'single_test')),
            target_role VARCHAR(100),
            target_city VARCHAR(100),
            template_body TEXT NOT NULL,
            total_recipients INT NOT NULL DEFAULT 0,
            sent_count INT NOT NULL DEFAULT 0,
            failed_count INT NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PAUSED')),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_sms_campaigns_status ON sms_campaigns(status, created_at DESC);

        CREATE TABLE IF NOT EXISTS sms_dispatch_logs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            campaign_id UUID REFERENCES sms_campaigns(id) ON DELETE SET NULL,
            device_id UUID REFERENCES paired_devices(id) ON DELETE SET NULL,
            candidate_name VARCHAR(150),
            candidate_phone VARCHAR(20) NOT NULL,
            candidate_role VARCHAR(100),
            message_body TEXT NOT NULL,
            char_count SMALLINT NOT NULL,
            credit_units SMALLINT NOT NULL DEFAULT 1,
            gateway_mode VARCHAR(20) NOT NULL CHECK (gateway_mode IN ('webusb', 'qr_wireless', 'http_apk', 'daemon', 'adb')),
            sim_carrier VARCHAR(50),
            status VARCHAR(20) NOT NULL CHECK (status IN ('QUEUED', 'SENT', 'FAILED', 'BLOCKED_QUOTA')),
            error_reason TEXT,
            dispatched_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_sms_logs_phone ON sms_dispatch_logs(candidate_phone);
        CREATE INDEX IF NOT EXISTS idx_sms_logs_status_dispatched ON sms_dispatch_logs(status, dispatched_at DESC);
        CREATE INDEX IF NOT EXISTS idx_sms_logs_campaign_id ON sms_dispatch_logs(campaign_id);
        """
    ),
    (
        "002_add_delivery_metrics_and_app_meta",
        """
        -- Safe incremental column additions (Never drops or modifies existing data)
        ALTER TABLE sms_dispatch_logs ADD COLUMN IF NOT EXISTS dispatch_latency_ms INT DEFAULT 0;
        ALTER TABLE sms_dispatch_logs ADD COLUMN IF NOT EXISTS sim_slot SMALLINT DEFAULT 1;
        ALTER TABLE paired_devices ADD COLUMN IF NOT EXISTS battery_level SMALLINT DEFAULT 100;
        ALTER TABLE paired_devices ADD COLUMN IF NOT EXISTS app_version VARCHAR(20) DEFAULT '1.0.0';
        """
    ),
    (
        "003_add_auth_and_templates",
        """
        -- Team Users Table
        CREATE TABLE IF NOT EXISTS studio_users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'recruiter',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Saved SMS Templates Table (Private + Shared)
        CREATE TABLE IF NOT EXISTS sms_templates (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID REFERENCES studio_users(id) ON DELETE SET NULL,
            title VARCHAR(100) NOT NULL,
            category VARCHAR(50) NOT NULL DEFAULT 'recruitment',
            visibility VARCHAR(20) NOT NULL DEFAULT 'public' CHECK (visibility IN ('public', 'private')),
            template_body TEXT NOT NULL,
            char_count SMALLINT NOT NULL DEFAULT 0,
            usage_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_sms_templates_category ON sms_templates(category);
        CREATE INDEX IF NOT EXISTS idx_sms_templates_visibility ON sms_templates(visibility);
        """
    )
]

class SchemaMigrator:
    @staticmethod
    def run_auto_migrations():
        if not DB_URL:
            print("[Migration] SUPABASE_DB_URL not found. Skipping database migration.")
            return

        print("[Migration] Checking Supabase database schema evolution...")
        try:
            conn = psycopg2.connect(DB_URL, connect_timeout=10)
            conn.autocommit = True
            cur = conn.cursor()

            # 1. Ensure migrations metadata table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _schema_migrations (
                    id SERIAL PRIMARY KEY,
                    version VARCHAR(100) UNIQUE NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    execution_time_ms INT NOT NULL DEFAULT 0
                );
            """)

            # 2. Get list of already applied migrations
            cur.execute("SELECT version FROM _schema_migrations")
            applied = set(row[0] for row in cur.fetchall())

            # 3. Apply pending migrations
            applied_count = 0
            for version, sql in MIGRATIONS:
                if version not in applied:
                    start_t = time.time()
                    print(f" [Migration] Running pending migration: {version}...")
                    cur.execute(sql)
                    elapsed_ms = int((time.time() - start_t) * 1000)
                    cur.execute(
                        "INSERT INTO _schema_migrations (version, execution_time_ms) VALUES (%s, %s)",
                        (version, elapsed_ms)
                    )
                    applied_count += 1
                    print(f" [Migration] Migration {version} applied successfully in {elapsed_ms}ms! (Data intact)")

            if applied_count == 0:
                print(f"[Migration] Supabase Database is 100% UP TO DATE ({len(applied)} migrations verified).")
            else:
                print(f"[Migration] Successfully applied {applied_count} new migration(s).")

            conn.close()
        except Exception as e:
            print(f"[Migration Error] Could not run automatic migrations: {e}")

if __name__ == "__main__":
    SchemaMigrator.run_auto_migrations()
