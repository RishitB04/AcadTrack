# 🎓 AcadTrack: Student CPI and Credit Management System

A web-based academic tracking system that allows students to manage their academic progress and administrators to manage course enrollment and grading. Developed using **Flask** and **SQLite**.

## 📌 Features

### 👨‍🎓 Student Features

- **Student Login**: Log in using a unique student ID.
- **Dashboard**: View current and past enrolled courses, earned credits, and academic progress.
- **SPI/CPI Calculation**:
  - **SPI** (Semester Performance Index): Credit-weighted average for each semester.
  - **CPI** (Cumulative Performance Index): Based on most recent attempts of all courses.
- **Course Enrollment**: Allowed during open enrollment periods.
- **Graduation Eligibility**:
  - No failed or pending grades.
  - Required credits fulfilled in IC (Institutional Core), DE (Departmental Elective), and OE (Open Elective).

### 🛠 Admin Features

- **Admin Login**: Secure access using designated admin ID.
- **Dashboard**: View and filter students and courses by batch or type.
- **Batch Management**:
  - Upload new student batches (only in Semester 1).
  - Auto-generate student IDs.
- **Course Management**: Add new courses with validation against duplicates.
- **Enrollment Control**:
  - Manually open/close enrollment per semester.
- **Grade Submission**:
  - Allowed only after enrollment closes.
  - Submit grades for student-course pairs.
  - Automatically advance semester once all grades are submitted.
- **Automatic Semester Advancement**:
  - Semester updates when all grades are in.
  - Next semester enrollment is opened by default.

## 🧱 Technology Stack

- **Backend**: Python (Flask)
- **Database**: SQLite
- **Frontend**: HTML + Jinja2 templating
- **Deployment**: Local VM with NAT port forwarding

## 🗃️ Database Design

- `Students (student_id, name, batch_id)`
- `Courses (course_id, name, credits, course_type)`
- `Enrollments (student_id, course_id, year, semester, grade)`
- `Batches (batch_id, batch_year)`
- `CurriculumRequirements (course_type, required_credits)`
- `Session (id, year, semester)`
- `EnrollmentStatus (year, semester, is_enrollment_open)`

## 🔮 Future Improvements

- JWT-based login for multiple concurrent sessions
- Role-based access using decorators
- Bulk upload of student/course data via CSV
- AJAX-based interfaces for smoother UX

## 📘 Conclusion

AcadTrack offers a robust framework for academic record management and semester progression. Its modular architecture and scalable schema make it ideal for deployment in educational institutions.

---
