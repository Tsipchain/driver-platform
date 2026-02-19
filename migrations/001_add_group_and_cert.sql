-- SQLite migration for group/cert parity
ALTER TABLE trips ADD COLUMN company_name TEXT;
ALTER TABLE trips ADD COLUMN group_tag TEXT;
CREATE INDEX IF NOT EXISTS idx_trips_group_tag ON trips(group_tag);
CREATE TABLE IF NOT EXISTS certifications (
  id INTEGER PRIMARY KEY,
  driver_id INTEGER NOT NULL,
  cert_type TEXT NOT NULL,
  cert_ref TEXT NULL,
  issued_at DATETIME NOT NULL,
  FOREIGN KEY(driver_id) REFERENCES drivers(id)
);
