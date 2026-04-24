-- Create a separate database for LiteLLM so its Prisma migrations
-- cannot interfere with AgentBreeder's Alembic-managed schema.
SELECT 'CREATE DATABASE litellm OWNER agentbreeder'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'litellm')\gexec
