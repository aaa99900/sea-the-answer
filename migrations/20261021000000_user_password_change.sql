-- Existing accounts and restored legacy backups must rotate their initial password.
-- migrate:up
ALTER TABLE users ADD COLUMN must_change_password boolean NOT NULL DEFAULT true;

-- migrate:down
ALTER TABLE users DROP COLUMN must_change_password;
