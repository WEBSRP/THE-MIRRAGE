-- ====================================================================
-- MIRRAGE Production Database Migration: Email OTP & Passwordless Auth
-- ====================================================================
-- Target: PostgreSQL (AWS RDS)
-- Safe & Idempotent: Can be run multiple times without data loss.
-- ====================================================================

-- 1. Add email_verified flag to users table (default false for existing users)
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false;

-- 2. Allow passwordless accounts (nullable hashed_password for OTP-only signups)
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- 3. Create the OTP storage table
CREATE TABLE IF NOT EXISTS otp_codes (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    code_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    is_used BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 4. Create lookup index on normalized email for rapid OTP retrieval & rate-limiting
CREATE INDEX IF NOT EXISTS ix_otp_codes_email ON otp_codes(email);
