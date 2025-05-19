-- Drop tables if they exist (for development purposes)
DROP TABLE IF EXISTS Enrollments;
DROP TABLE IF EXISTS Students;
DROP TABLE IF EXISTS Courses;
DROP TABLE IF EXISTS Batches;
DROP TABLE IF EXISTS CurriculumRequirements;
DROP TABLE IF EXISTS Session;
DROP TABLE IF EXISTS EnrollmentStatus;

-- 🧑 Students Table
CREATE TABLE Students (
    student_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    batch_id INTEGER NOT NULL,
    FOREIGN KEY (batch_id) REFERENCES Batches(batch_id)
);

-- 📆 Batches Table
CREATE TABLE Batches (
    batch_id INTEGER PRIMARY KEY,
    batch_year INTEGER NOT NULL
);

-- 📘 Courses Table
CREATE TABLE Courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    credits INTEGER NOT NULL,
    course_type TEXT CHECK (course_type IN ('IC', 'DE', 'OE')) NOT NULL
);

-- 📝 Enrollments Table (includes grade + semester/year)
CREATE TABLE Enrollments (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL CHECK (semester IN (1, 2)),
    grade REAL CHECK (grade BETWEEN 0 AND 10),
    FOREIGN KEY (student_id) REFERENCES Students(student_id),
    FOREIGN KEY (course_id) REFERENCES Courses(course_id)
);

-- 🎓 Curriculum Requirements (IC/DE/OE credit requirements)
CREATE TABLE CurriculumRequirements (
    course_type TEXT PRIMARY KEY CHECK (course_type IN ('IC', 'DE', 'OE')),
    required_credits INTEGER NOT NULL
);

-- 🕒 Current Session Table (holds current semester/year)
CREATE TABLE Session (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL CHECK (semester IN (1, 2))
);

-- Pre-fill curriculum credit requirements
INSERT INTO CurriculumRequirements (course_type, required_credits) VALUES
('DE', 10),
('OE', 10),
('IC', 10);

-- Insert default session (initial state)
INSERT INTO Session (id, year, semester) VALUES (1, 2024, 1);

CREATE TABLE EnrollmentStatus (
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    is_enrollment_open BOOLEAN DEFAULT 0,
    PRIMARY KEY (year, semester)
);