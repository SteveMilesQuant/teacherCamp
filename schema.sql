DROP TABLE IF EXISTS user;
CREATE TABLE user (
	id BIGINT PRIMARY KEY,
	given_name TEXT,
	family_name TEXT,
	full_name TEXT,
	primary_email TEXT,
	picture TEXT
);

DROP TABLE IF EXISTS user_x_roles;
create table user_x_roles (
	id BIGINT NOT NULL,
	role TEXT,
	FOREIGN KEY (id) REFERENCES user(id)
);

DROP TABLE IF EXISTS role_permissions;
CREATE TABLE role_permissions (
	role TEXT NOT NULL,
	endpoint TEXT
);
INSERT INTO role_permissions (role, endpoint) VALUES
	("GUARDIAN", "/programs/find"),
	("GUARDIAN", "/programs/enrolled"),
	("GUARDIAN", "/students"),
	("INSTRUCTOR", "/programs/teach"),
	("INSTRUCTOR", "/programs/design"),
	("ADMIN", "/members"),
	("ADMIN", "/database"),
	("ADMIN", "/programs/location"),
	("ADMIN", "/programs/schedule");



