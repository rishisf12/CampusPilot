-- Timetable SQL Seeder
-- Generated automatically from parsed timetable data

DELETE FROM academic.timetable_slot;

INSERT INTO academic.timetable_slot (day, start_time, end_time, room, course_code, instructor, branch_or_program, semester, remarks) VALUES ('Mon', '10:00', '10:55', 'L102', 'NS1002', 'MKR', 'CSE A', 1, NULL);
INSERT INTO academic.timetable_slot (day, start_time, end_time, room, course_code, instructor, branch_or_program, semester, remarks) VALUES ('Mon', '11:00', '11:55', 'L102', 'HS1001', 'JAMF', 'CSE A', 1, 'Tutorial');