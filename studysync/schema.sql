-- StudySync relational schema (SQLite). Mirrors the Week 1 ER diagram; tags and RSVPs are
-- separate tables because SQL has no embedded arrays. All foreign keys are enforced.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'admin')),
  avatar_url    TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_groups (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT NOT NULL,
  subject     TEXT NOT NULL,
  visibility  TEXT NOT NULL CHECK (visibility IN ('public', 'private')),
  invite_code TEXT NOT NULL UNIQUE,
  owner_id    TEXT NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_groups_discovery ON study_groups(visibility, subject);

CREATE TABLE IF NOT EXISTS memberships (
  id        TEXT PRIMARY KEY,
  group_id  TEXT NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
  user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role      TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'moderator', 'member')),
  joined_at TEXT NOT NULL,
  UNIQUE (group_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);
-- A group has exactly one owner (enforced by the database, not just by service code).
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_owner_per_group ON memberships(group_id) WHERE role = 'owner';

CREATE TABLE IF NOT EXISTS resources (
  id          TEXT PRIMARY KEY,
  group_id    TEXT NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
  uploaded_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  title       TEXT NOT NULL,
  type        TEXT NOT NULL CHECK (type IN ('link', 'file', 'note')),
  url         TEXT NOT NULL DEFAULT '',
  body        TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL,
  updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_resources_group ON resources(group_id, created_at);

CREATE TABLE IF NOT EXISTS resource_tags (
  resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
  tag         TEXT NOT NULL,
  PRIMARY KEY (resource_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_resource_tags_tag ON resource_tags(tag);

CREATE TABLE IF NOT EXISTS posts (
  id         TEXT PRIMARY KEY,
  group_id   TEXT NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
  author_id  TEXT REFERENCES users(id) ON DELETE SET NULL,
  title      TEXT NOT NULL,
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_group ON posts(group_id, created_at);

CREATE TABLE IF NOT EXISTS comments (
  id         TEXT PRIMARY KEY,
  post_id    TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  author_id  TEXT REFERENCES users(id) ON DELETE SET NULL,
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_at);

CREATE TABLE IF NOT EXISTS study_sessions (
  id           TEXT PRIMARY KEY,
  group_id     TEXT NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
  created_by   TEXT REFERENCES users(id) ON DELETE SET NULL,
  title        TEXT NOT NULL,
  starts_at    TEXT NOT NULL,
  duration_min INTEGER NOT NULL CHECK (duration_min BETWEEN 15 AND 300),
  meeting_link TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL,
  updated_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_group ON study_sessions(group_id, starts_at);

CREATE TABLE IF NOT EXISTS session_attendees (
  session_id TEXT NOT NULL REFERENCES study_sessions(id) ON DELETE CASCADE,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status     TEXT NOT NULL CHECK (status IN ('going', 'maybe', 'no')),
  PRIMARY KEY (session_id, user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type       TEXT NOT NULL CHECK (type IN ('info', 'resource', 'post', 'reply', 'session', 'member')),
  message    TEXT NOT NULL,
  link       TEXT NOT NULL DEFAULT '',
  is_read    INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created_at);

-- Refresh tokens are stored only as SHA-256 hashes. All tokens issued from one login share a family_id
-- so that re-use of an already-rotated token can revoke the whole family.
CREATE TABLE IF NOT EXISTS refresh_tokens (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  family_id  TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refresh_family ON refresh_tokens(family_id);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);
