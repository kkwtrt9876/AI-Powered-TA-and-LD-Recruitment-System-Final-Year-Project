CREATE DATABASE flask_app;
USE flask_app;

CREATE TABLE students (
    s_id VARCHAR(50) PRIMARY KEY,
    password VARCHAR(50)
);

DELETE FROM student_sgpa WHERE s_id = 'i221944';
DELETE FROM student_studied_courses WHERE student_id = 'i221944';
DELETE FROM students WHERE s_id = 'i221944';


SHOW COLUMNS FROM student_studied_courses;

SELECT * FROM student_applications_TA;


CREATE TABLE student_studied_courses (  -- more of the columns will be assed in it 
    student_id VARCHAR(50),
    sem_id varchar(50),
    
    
    -- Introduction_to_Information_and_Communication_Technologies VARCHAR(50) default 0,   -- 1 that he has studied , 1-2-3- semester no , 123 credit hrs
--     Data_Structures_Lab VARCHAR(50) default 0,
--     Programming_Fundamentals_Lab VARCHAR(50) default 0,
--     Computer_Organization_and_Assembly_Language_Lab varchar(50) default 0,
--     Programming_for_Artificial_Intelligence_Lab varchar(50) default 0,
--     Introduction_to_Data_Science_Lab varchar(50) default 0,
--     Digital_Logic_Design_Lab varchar(50) default 0,
--     Object_Oriented_Programming_Lab varchar(50) default 0,
--     Computer_Networks_Lab varchar(50) default 0,
--     Machine_Learning_Lab varchar(50) default 0,
--     Operating_Systems_Lab varchar(50) default 0,
--     Data_Analysis_and_Visualization_Lab varchar(50) default 0,
--     Data_Warehousing_and_Business_Intelligence_Lab varchar(50) default 0,
--     Database_Systems_Lab varchar(50) default 0,
--     Network_Security_Lab varchar(50) default 0,
--     Computer_Vision_Lab varchar(50) default 0,
--     Secure_Software_Design_Lab varchar(50) default 0,
--     Software_Construction_and_Development_Lab varchar(50) default 0,
    
    
    FOREIGN KEY (student_id) REFERENCES students(s_id),
    FOREIGN KEY (sem_id) REFERENCES semester_id_data(semester_id)
);

insert into helper_student_studied_courses values 
("Introduction to Information & Communication Technologies","Introduction_to_Information_and_Communication_Technologies"),
("Data Structures Lab","Data_Structures_Lab"),
("Programming Fundamentals Lab","Programming_Fundamentals_Lab"),
("Computer Organization and Assembly Language Lab","Computer_Organization_and_Assembly_Language_Lab"),
("Programming for Artificial Intelligence Lab","Programming_for_Artificial_Intelligence_Lab"),
("Introduction to Data Science Lab","Introduction_to_Data_Science_Lab"),
("Digital Logic Design Lab","Digital_Logic_Design_Lab"),
("Object Oriented Programming Lab","Object_Oriented_Programming_Lab"),
("Computer Networks Lab","Computer_Networks_Lab"),
("Machine Learning Lab","Machine_Learning_Lab"),
("Operating Systems Lab","Operating_Systems_Lab"),
("Data Analysis & Visualization Lab","Data_Analysis_and_Visualization_Lab"),
("Data Warehousing & Business Intelligence Lab","Data_Warehousing_and_Business_Intelligence_Lab"),
("Database Systems Lab","Database_Systems_Lab"),
("Network Security Lab","Network_Security_Lab"),
("Computer Vision Lab","Computer_Vision_Lab"),
("Secure Software Design Lab","Secure_Software_Design_Lab"),
("Software Construction and Development Lab","Software_Construction_and_Development_Lab");

select * from ld_courses_display;	

drop table student_studied_courses;

truncate table student_studied_courses;
truncate table students;
truncate student_gpa;
insert into student_studied_courses(student_id) value ("i221944");
select * from student_studied_courses;

-- oop_lab int default 0,
-- programming_fundamentals_lab int default 0,
-- data_base_systems_lab int default 0,
-- artificial_intellegence_lab int default 0,
-- computer_networks_lab

ALTER TABLE student_studied_courses ADD COLUMN computer_networks_lab VARCHAR(50) DEFAULT '0';

drop table helper_student_studied_courses;
insert into helper_student_studied_courses values 
("Object Oriented Programming lab","oop_lab"),
("Programming Fundamentals lab","programming_fundamentals_lab"),
("Data Base System lab","data_base_systems_lab"),
("Artificial Intelligence lab","artificial_intellegence_lab"),
("Computer Networks lab","computer_networks_lab");

select data_structure from student_studied_courses where student_id = "i221944";
select * from helper_student_studied_courses;

create table helper_student_studied_courses(
name varchar(150),
column_name varchar(150));

select * from helper_student_studied_courses;
select * from departments;

insert into helper_student_studied_courses values ("Data Structure","data_structure"),
("Object Oriented Programming","oop"),
("Programming Fundamentals","programming_fundamentals"),
("Data Base System","data_base_systems"),
("Algorithms","algorithms"),
("Artificial Intelligence","artificial_intellegence"),
("Computer Networks","computer_networks");



create table student_department(
s_id varchar(50),
dep_id int,
foreign key (s_id) references students(s_id),
foreign key (dep_id) references departments(dep_id));

truncate table student_department;

create table login_details(
username varchar(50),
password varchar(50),
role varchar(50),
time datetime);

select * from login_details;

select * from student_department;

create table departments(
dep_id int primary key auto_increment,
dep_name varchar(50));

select * from departments;

select * from student_applications;

UPDATE helper_student_studied_courses
SET column_name = ''
WHERE dep_name = 'computer science';

insert into departments (dep_name) values ("Cyber Security");
insert into departments (dep_name) values ("Artificial Intellegence") , ("Software Engineering");
select * from student_department;
create table student_sgpa(
s_id varchar(50),
sem_id varchar(50),
s_gpa decimal(3,2),
foreign key (s_id) references students(s_id)
);

truncate table student_gpa;
truncate table student_sgpa;
truncate table student_studied_courses;
select * from student_sgpa;
truncate table student_sgpa;
create table semester_id_data(
semester_id varchar(50) primary key);

select * from semester_id_data;

SELECT * FROM student_gpa where s_id = 'i221940';

INSERT INTO semester_id_data (semester_id) VALUES
('Spring 2020'),
('Summer 2020'),
('Fall 2020'),
('Spring 2021'),
('Summer 2021'),
('Fall 2021'),
('Spring 2022'),
('Summer 2022'),
('Fall 2022'),
('Spring 2023'),
('Summer 2023'),
('Fall 2023'),
('Spring 2024'),
('Summer 2024'),
('Fall 2024'),
('Spring 2025'),
('Summer 2025'),
('Fall 2025');

select * from semester_id_data;


select * from departments;


create table student_gpa(
s_id varchar(50),
gpa float,
upper_part float,
lower_part int,
foreign key (s_id) references students(s_id));
select * from student_gpa;
insert into student_gpa(s_id,gpa,upper_part,lower_part) values ('i221944',3.12,132.2,34);


truncate table student_gpa;
drop table student_gpa;

select * from student_studied_courses_helper;

truncate table student_studied_courses;


drop table student_studied_courses;

INSERT INTO students  VALUE
('i221944', '123');

select * from students;

create table admins(
a_id varchar(50) primary key,
password varchar(50));

insert into admins values ('admin',123);
select * from admins;

CREATE TABLE IF NOT EXISTS launch_selection (
  id INT AUTO_INCREMENT PRIMARY KEY,
  launch_datetime DATETIME NOT NULL,
  result_datetime DATETIME NOT NULL,
  results int default 0,
  semester_id varchar(50),
	FOREIGN KEY (semester_id) REFERENCES semester_id_data(semester_id)
);



drop table launch_selection;
truncate table launch_selection;
select * from launch_selection;



CREATE TABLE IF NOT EXISTS launch_selection_TA(
  id INT AUTO_INCREMENT PRIMARY KEY,
  launch_datetime DATETIME NOT NULL,
  result_datetime DATETIME NOT NULL,
  results int default 0,
  semester_id varchar(50),
	FOREIGN KEY (semester_id) REFERENCES semester_id_data(semester_id)
);


insert into student_studied_courses(course_col,student_id,sem_id) values ('','','');


CREATE TABLE IF NOT EXISTS ld_timeout_acceptance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  launch_datetime DATETIME NOT NULL,
  result_datetime DATETIME NOT NULL
);


CREATE TABLE IF NOT EXISTS TA_timeout_acceptance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  launch_datetime DATETIME NOT NULL,
  result_datetime DATETIME NOT NULL
);




CREATE TABLE student_applications (
    
    username VARCHAR(150) NOT NULL,
    course_code VARCHAR(150) NOT NULL,
    launch_id INT NOT NULL,
    time_apply DATETIME NOT NULL,
    semester_id varchar(50),
   
    section varchar(50),
    FOREIGN KEY (semester_id) REFERENCES semester_id_data(semester_id)
  
    
);


ALTER TABLE student_applications
ADD COLUMN interview_taken TINYINT(1) DEFAULT 0,
ADD COLUMN interview_marks INT DEFAULT 0;

use flask_app;
ALTER TABLE student_applications
ADD COLUMN submission_files_path VARCHAR(255) DEFAULT NULL;

ALTER TABLE student_applications_ta
ADD COLUMN submission_files_path VARCHAR(255) DEFAULT NULL;

select * from student_applications_ta;


select * from departments;

SELECT course_code FROM student_applications
                WHERE username = 'i221940' AND launch_id = 13 AND semester_id ='Fall 2025' and dep_id=1 and section='BSE-1D';

drop table student_applications_TA;
use Flask_app;
ALTER TABLE student_applications_TA
ADD COLUMN interview_taken TINYINT(1) DEFAULT 0,
ADD COLUMN interview_marks INT DEFAULT 0;

CREATE TABLE student_applications_TA (
    
    username VARCHAR(100) NOT NULL,
    course_code VARCHAR(100) NOT NULL,
    launch_id INT NOT NULL,
    time_apply DATETIME NOT NULL,
    semester_id varchar(50),

    section varchar(50),
    FOREIGN KEY (semester_id) REFERENCES semester_id_data(semester_id)
);

select * from student_applications_TA where username = 'i221941';

select * from student_applications_TA;
drop table student_applications_TA;
select * from helper_student_studied_courses;

select * from lab_allocations;
select * from ld_finalization;

CREATE TABLE lab_allocations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sem_id varchar(50),
    lab_name VARCHAR(150),
    column_name varchar(150),
    section VARCHAR(20),
    
    lab_instructor VARCHAR(100),
    lab_instructor_id varchar(100),
    strength varchar(10),
    s_id_one VARCHAR(50),
    email_one VARCHAR(100),
    confirmed_one int default 0,
    s_id_two VARCHAR(50),
    email_two VARCHAR(100),
    confirmed_two int default 0,
    allocation_count INT DEFAULT 0,
    
    FOREIGN KEY (sem_id) REFERENCES semester_id_data(semester_id),
    foreign key (s_id_one) references students(s_id),
    foreign key (s_id_two) references students(s_id)
);

drop table lab_allocations;

drop table lab_allocations;
drop table helper_student_studied_courses;

CREATE TABLE TA_allocations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sem_id varchar(50),
    course_name VARCHAR(150),
    column_name varchar(150),
    section VARCHAR(20),
    
    course_instructor VARCHAR(100),
    course_instructor_id VARCHAR(100),
    
    CHs int,
    s_id VARCHAR(50),
    email VARCHAR(100),
    allocation_count INT DEFAULT 0,
    confirmed int default 0,
    FOREIGN KEY (sem_id) REFERENCES semester_id_data(semester_id),
    foreign key (s_id) references students(s_id)
);
select * from TA_allocations;
select * from ld_finalization;

select * from lab_allocations;
select * from student_applications;
select * from TA_allocations;
select * from student_studied_courses;
select * from helper_student_studied_courses;
drop table lab_allocations;
UPDATE departments
SET dep_name = 'Artificial Intelligence'
WHERE dep_name = 'Artificial Intellegence';

select distinct section , department from lab_allocations where column_name = 'Introduction_to_Information_and_Communication_Technologies';

select * from helper_student_studied_courses;

select * from TA_results_for_Teacher;

select * from TA_allocations;
drop table TA_results_for_Teacher;

CREATE TABLE IF NOT EXISTS TA_results_for_Teacher (
    id INT AUTO_INCREMENT PRIMARY KEY,
    semester VARCHAR(50) NOT NULL,           -- Current semester
    course_code VARCHAR(150) NOT NULL,       -- Course code
    section VARCHAR(50) NOT NULL,           -- Section
    launch_id INT NOT NULL,                 -- TA launch ID
    student_id VARCHAR(50) NOT NULL,        -- Student username
    time_apply DATETIME NOT NULL,           -- When student applied
    gpa DECIMAL(3,2) NOT NULL,             -- Student GPA
    grade DECIMAL(4,2) NOT NULL,           -- Course grade
    seniority INT NOT NULL,                 -- Number of semesters studied (excluding summer)
    rank_ INT NOT NULL,                      -- Rank in this course-section
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acceptance int default 0
);

ALTER TABLE ta_allocations
ADD COLUMN submission_files_path VARCHAR(255) DEFAULT NULL;

select * from teacher_login where id = '4178@nu.edu.pk';

select * from ta_Allocations;
select * from TA_results_for_Teacher;

select * from TA_results_for_Teacher;
select * from TA_allocations;

drop table student_applications;
select * from student_applications where username = 'i221920' and launch_id=29;

select * from student_applications inner join student_studied_courses on student_applications.username = student_studied_courses.student_id where launch_id = 3;
select * from student_studied_courses;

select programming_fundamentals from student_studied_courses where student_id = 'i221920';

select * from ld_courses_display;

create table ld_courses_display(
sem_id varchar(50),
s_id varchar(50),
course_name varchar(150),
section varchar(50),
acceptance int,
launch_id int,
FOREIGN KEY (s_id) REFERENCES semester_id_data(semester_id),
FOREIGN KEY (sem_id) REFERENCES students(s_id));


select * from ld_finalization;
drop table ld_courses_display;
select * from TA_courses_display;
ALTER TABLE student_studied_courses ADD COLUMN computer_networks_lab VARCHAR(50) DEFAULT '0';

select * from TA_allocations;
select * from TA_results_for_Teacher;

SELECT sem_id, course_name, column_name, section,
               course_instructor, course_instructor_id
        FROM TA_allocations
        WHERE course_instructor_id = '4178@nu.edu.pk' and sem_id='Spring 2026'
        ORDER BY course_name, section;

update TA_allocations set sem_id = 'Spring 2026';


SELECT * FROM student_applications;

create table TA_courses_display(
sem_id varchar(50),

FOREIGN KEY (sem_id) REFERENCES semester_id_data(semester_id));





drop table ld_courses_display;
select * from TA_courses_display;
select * from launch_selection;


create table ld_finalization(
sem_id varchar(50),
s_id varchar(50),
course_name varchar(150),
section varchar(50),
acceptance int default 0,
launch_id int,
number int,
FOREIGN KEY (sem_id) REFERENCES semester_id_data(semester_id),
FOREIGN KEY (s_id) REFERENCES students(s_id));	

ALTER TABLE ld_finalization
ADD COLUMN submission_files_path VARCHAR(255) DEFAULT NULL;



select * from student_applications_TA;

drop table ld_finalization;
use flask_app;
select * from lab_allocations;

update lab_allocations set allocation_count =0;
truncate table ld_finalization;
select * from ld_finalization where sem_id='Fall 2025' and s_id = 'i221920' and launch_id = 31;
select * from ld_finalization;
drop table ld_finalization;

create table ld_course_details(
sem_id varchar(50),
course_name varchar(50),
counter_lds int default 0,
launch_times int default 0,
FOREIGN KEY (sem_id) REFERENCES semester_id_data(semester_id));

select * from ld_course_details;
truncate table ld_course_details;

select * from lab_allocations;






-- truncation done 
truncate table lab_allocations;
truncate table ld_finalization;
truncate table student_ld_counter;
truncate table TA_allocations;
truncate table student_TA_counter;

select * from TA_allocations;

select * from lab_allocations;








select * from ld_finalization;


## small issue is present 

create table student_ld_counter(
sem_id varchar(50),
s_id varchar(50),
counter int default 0,
FOREIGN KEY (sem_id) REFERENCES semester_id_data(semester_id));

create table student_TA_counter(
sem_id varchar(50),
s_id varchar(50),
counter int default 0,
FOREIGN KEY (sem_id) REFERENCES semester_id_data(semester_id));

select * from student_TA_counter;



-- SELECT * FROM ld_finalization 
--     WHERE sem_id = 'Fall 2025' AND s_id = 'i221920' AND launch_id = 34;

select * from ld_finalization;

select * from student_applications;

truncate table ld_finalization;

select * from student_ld_counter;
truncate table student_ld_counter;

truncate table ld_timeout_acceptance;
-- a small issue is present in the launching of the courses , it launches directly


select * from TA_allocations;

create table teacher_login(
name varchar(100),
id varchar(50),
password varchar(50));

select * from teacher_login;

select * from student_TA_counter;

truncate table teacher_login;

use flask_app;
select * from teacher_login where id = '4178@nu.edu.pk';

select * from lab_allocations;

select * from ld_finalization;

select * from ld_finalization;

ALTER TABLE lab_allocations
ADD COLUMN submission_files_path VARCHAR(255) DEFAULT NULL;

ALTER TABLE lab_allocations
ADD COLUMN submission_files_path1 VARCHAR(255) DEFAULT NULL;