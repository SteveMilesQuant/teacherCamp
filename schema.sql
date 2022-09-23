DROP TABLE IF EXISTS user;
CREATE TABLE user (
	id BIGINT PRIMARY KEY,
	given_name TEXT,
	family_name TEXT,
	full_name TEXT,
	google_email TEXT,
	picture TEXT
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

DROP TABLE IF EXISTS user_x_roles;
create table user_x_roles (
	user_id BIGINT NOT NULL,
	role TEXT,
	FOREIGN KEY (user_id) REFERENCES user(id)
);

DROP TABLE IF EXISTS student;
create table student (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	birthdate DATE,
	school text
);

DROP TABLE IF EXISTS user_x_students;
create table user_x_students (
	user_id BIGINT NOT NULL,
	student_id INTEGER NOT NULL,
	FOREIGN KEY (user_id) REFERENCES user(id)
	FOREIGN KEY (student_id) REFERENCES student(id)
)



