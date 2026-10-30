-- Run in MySQL Workbench as an administrator. No existing data is dropped.
CREATE DATABASE IF NOT EXISTS `Default_Credit`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Optional dedicated account: replace the placeholder locally, never commit a password.
-- CREATE USER 'creditrisk_app'@'localhost' IDENTIFIED BY 'REPLACE_LOCALLY';
-- GRANT SELECT, INSERT, CREATE, REFERENCES, INDEX ON `Default_Credit`.*
--   TO 'creditrisk_app'@'localhost';

USE `Default_Credit`;
-- Application creates the five tables on startup with SQLAlchemy metadata.
-- After starting the application, refresh SCHEMAS and inspect:
-- SELECT * FROM datasets;
-- SELECT * FROM dataset_versions;
-- SELECT * FROM prediction_runs ORDER BY id DESC;
