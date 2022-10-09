DROP TABLE IF EXISTS user;
CREATE TABLE user (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	google_id BIGINT NOT NULL,
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
	("GUARDIAN",	"/students",	"My Students"),
	("GUARDIAN",	"/camps",		"Find Camps"),
	("INSTRUCTOR",	"/teach",		"Ongoing Camps"),
	("INSTRUCTOR",	"/programs",	"Design Programs"),
	("ADMIN",		"/members",		"Manage Members"),
	("ADMIN",		"/database",	"Manage Database"),
	("ADMIN",		"/schedule",	"Schedule Camps");

DROP TABLE IF EXISTS user_x_roles;
create table user_x_roles (
	user_id INTEGER NOT NULL,
	role TEXT,
	FOREIGN KEY (user_id) REFERENCES user(id)
);

DROP TABLE IF EXISTS student;
create table student (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	birthdate DATE,
	grade_level INT,
	school text
);

DROP TABLE IF EXISTS user_x_students;
create table user_x_students (
	user_id INTEGER NOT NULL,
	student_id INTEGER NOT NULL,
	FOREIGN KEY (user_id) REFERENCES user(id),
	FOREIGN KEY (student_id) REFERENCES student(id)
);

DROP TABLE IF EXISTS program;
create table program (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	title TEXT,
	from_grade INTEGER,
	to_grade INTEGER,
	tags TEXT,
	description TEXT
);

DROP TABLE IF EXISTS user_x_programs;
create table user_x_programs (
	user_id INTEGER NOT NULL,
	program_id INTEGER NOT NULL,
	FOREIGN KEY (user_id) REFERENCES user(id),
	FOREIGN KEY (program_id) REFERENCES program(id)
);

DROP TABLE IF EXISTS level;
create table level (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	title TEXT,
	description TEXT,
	list_index INTEGER
);

DROP TABLE IF EXISTS program_x_levels;
create table program_x_levels (
	program_id INTEGER NOT NULL,
	level_id INTEGER NOT NULL,
	FOREIGN KEY (program_id) REFERENCES program(id),
	FOREIGN KEY (level_id) REFERENCES level(id)
);

DROP TABLE IF EXISTS camp;
create table camp (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	program_id INTEGER,
	FOREIGN KEY (program_id) REFERENCES program(id)
);

DROP TABLE IF EXISTS camp_x_instructors;
create table camp_x_instructors (
	camp_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	is_primary BOOL,
	FOREIGN KEY (camp_id) REFERENCES camp(id),
	FOREIGN KEY (user_id) REFERENCES user(id)
);
