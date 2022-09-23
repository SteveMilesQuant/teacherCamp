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
	endpoint TEXT,
	endpoint_title TEXT
);
INSERT INTO role_permissions (role, endpoint, endpoint_title) VALUES
	("GUARDIAN",	"/programs/find",		"Find Programs"),
	("GUARDIAN",	"/programs/enrolled",	"Enrolled Programs"),
	("GUARDIAN",	"/students",			"My Students"),
	("INSTRUCTOR",	"/programs/teach",		"My Programs"),
	("INSTRUCTOR",	"/programs/design",		"Design Programs"),
	("ADMIN",		"/members",				"Manage Members"),
	("ADMIN",		"/database",			"Manage Database"),
	("ADMIN",		"/programs/schedule",	"Schedule Programs");



