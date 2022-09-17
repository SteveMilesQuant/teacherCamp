DROP TABLE IF EXISTS user;

CREATE TABLE user (
  id BIGINT PRIMARY KEY,
  given_name TEXT,
  family_name TEXT,
  full_name TEXT,
  primary_email TEXT,
  picture TEXT
);


