-- Initial PostgreSQL setup for Sovereign AI Hub
-- This runs on first container start via docker-entrypoint-initdb.d

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Full-text search is built-in, no extension needed

-- Create a read-only role for audit log (no UPDATE/DELETE)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_reader') THEN
        CREATE ROLE audit_reader;
    END IF;
END
$$;
