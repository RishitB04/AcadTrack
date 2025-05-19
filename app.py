from flask import Flask, render_template, request, redirect, session, url_for, flash
from collections import defaultdict
import sqlite3
from datetime import timedelta

app = Flask(__name__)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.secret_key = '123'
DATABASE = 'database.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_enrollment_status():
    db=get_db()
    year,semester=get_current_session()
    status = db.execute('''
        SELECT is_enrollment_open FROM EnrollmentStatus
        WHERE year = ? AND semester = ?
    ''', (year, semester)).fetchone()

    if status is None:
    # No entry yet — treat as open and insert one
        is_enrollment_open = True
        db.execute('''
            INSERT INTO EnrollmentStatus (year, semester, is_enrollment_open)
            VALUES (?, ?, 1)
        ''', (year, semester))
        db.commit()
    else:
        is_enrollment_open = status['is_enrollment_open']
    return is_enrollment_open

def get_current_session():
    db = get_db()
    session_data = db.execute('SELECT year, semester FROM Session WHERE id = 1').fetchone()
    return session_data['year'], session_data['semester']

def advance_semester():
    db = get_db()
    year, semester = get_current_session()
    if semester == 1:
        db.execute('UPDATE Session SET semester = 2 WHERE id = 1')
    else:
        db.execute('UPDATE Session SET semester = 1, year = year + 1 WHERE id = 1')
    db.commit()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user_id = request.form['user_id']
        
        if user_id == '9999':
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        
        db = get_db()
        student = db.execute('SELECT * FROM Students WHERE student_id = ?', (user_id,)).fetchone()
        
        if student:
            session['role'] = 'student'
            session['student_id'] = user_id
            return redirect(url_for('student_dashboard'))
        else:
            error = 'Invalid ID. Please try again.'
    
    return render_template('login.html', error=error)

@app.route('/student/dashboard', methods=['GET', 'POST'])
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    user_id = session.get('student_id')  # updated key
    conn = get_db()
    cursor = conn.cursor()

    # Fetch student details
    cursor.execute("SELECT * FROM Students WHERE student_id = ?", (user_id,))
    student = cursor.fetchone()

    # Fetch current session (year and semester)
    current_year, current_sem = get_current_session()

    # Check enrollment status for the current semester
    cursor.execute("SELECT is_enrollment_open FROM EnrollmentStatus WHERE year = ? AND semester = ?", (current_year, current_sem))
    status = cursor.fetchone()
    enrollment_open = status and status[0]

    # Fetch all courses the student is enrolled in current semester
    cursor.execute("""
        SELECT c.name, c.course_type, c.credits, e.grade, e.year, e.semester
        FROM Enrollments e
        JOIN Courses c ON e.course_id = c.course_id
        WHERE e.student_id = ? AND e.year = ? AND e.semester = ?
    """, (user_id,current_year,current_sem))
    current_courses = [dict(zip(['name', 'course_type', 'credits', 'grade', 'year', 'semester'], row)) for row in cursor.fetchall()]

    # Fetch all courses (past and current)
    cursor.execute("""
        SELECT c.course_id,c.name, c.course_type, c.credits, e.grade, e.year, e.semester
        FROM Enrollments e
        JOIN Courses c ON e.course_id = c.course_id
        WHERE e.student_id = ?
        ORDER BY e.year, e.semester
    """, (user_id,))
    all_courses = [dict(zip(['course_id','name', 'course_type', 'credits', 'grade', 'year', 'semester'], row)) for row in cursor.fetchall()]

    latest_attempts = {}
    for course in all_courses:
        cid = course['course_id']
        attempt_sem = (course['year'], course['semester'])
        prev = latest_attempts.get(cid)
        if not prev or attempt_sem > (prev['year'], prev['semester']):
            latest_attempts[cid] = course

    # Fetch curriculum requirements for credit types (IC, DE, OE)
    cursor.execute("SELECT course_type, required_credits FROM CurriculumRequirements")
    required_credits = {row[0]: row[1] for row in cursor.fetchall()}

    # Calculate earned credits and check passing status
    earned_credits = {'IC': 0, 'DE': 0, 'OE': 0}
    total_credits = 0
    passed_all_courses = True

    for course in latest_attempts.values():
        grade   = course['grade']
        ctype   = course['course_type']
        credits = course['credits']

        if grade is None:
            # still pending
            passed_all_courses = False
        elif grade >= 4:
            # passed latest attempt
            earned_credits[ctype] += credits
            total_credits  += credits
        else:
            # failed latest attempt
            passed_all_courses = False

    # Calculate if the student has met graduation requirements (credits and passed all courses)
    is_graduated = True
    for course_type, required in required_credits.items():
        if earned_credits[course_type] < required:
            is_graduated = False  # Not enough credits in one of the course types

    # Restrict enrollment if the student has graduated
    if is_graduated and passed_all_courses:
        # Show graduation message and prevent further enrollment
        return render_template('graduation.html', student=student, all_courses=all_courses)

    # Fetch available courses (those the student is not already enrolled in this semester)
    cursor.execute("""
        SELECT course_id, name, credits, course_type FROM Courses
        WHERE course_id NOT IN (
            SELECT course_id FROM Enrollments
            WHERE student_id = ?
            AND ( (year = ? AND semester = ?) OR (grade >= 4) )
        )
    """, (user_id, current_year, current_sem))
    available_courses = [dict(zip(['course_id', 'name', 'credits', 'course_type'], row)) for row in cursor.fetchall()]
    # Handle enrollment in new course if form is submitted
    if request.method == 'POST' and enrollment_open:
        selected_course_id = request.form.get('course_id')

        # Check if the student is already enrolled in the selected course for this semester
        cursor.execute("""
            SELECT 1 FROM Enrollments 
            WHERE student_id = ? AND course_id = ? AND year = ? AND semester = ?
        """, (user_id, selected_course_id, current_year, current_sem))
        already_enrolled = cursor.fetchone()

        # Check if the student has completed the selected course in any past semester
        cursor.execute("""
            SELECT 1 FROM Enrollments 
            WHERE student_id = ? AND course_id = ? AND grade >= 4
        """, (user_id, selected_course_id))
        already_completed = cursor.fetchone()

        # Allow enrollment if the student is not already enrolled or completed the course (with any grade)
        if not already_enrolled and not already_completed:
            cursor.execute("""
                INSERT INTO Enrollments (student_id, course_id, year, semester, grade)
                VALUES (?, ?, ?, ?, NULL)
            """, (user_id, selected_course_id, current_year, current_sem))
            conn.commit()

            # Fetch the updated list of enrolled courses in current sem after successful enrollment
            cursor.execute("""
                SELECT c.name, c.course_type, c.credits, e.grade, e.year, e.semester
                FROM Enrollments e
                JOIN Courses c ON e.course_id = c.course_id
                WHERE e.student_id = ? AND e.year = ? AND e.semester = ?
            """, (user_id,current_year,current_sem))
            current_courses = [dict(zip(['name', 'course_type', 'credits', 'grade', 'year', 'semester'], row)) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT course_id, name, credits, course_type FROM Courses
                WHERE course_id NOT IN (
                    SELECT course_id FROM Enrollments
                    WHERE student_id = ?
                    AND ( (year = ? AND semester = ?) OR (grade >= 4) )
                )
            """, (user_id, current_year, current_sem))
            available_courses = [dict(zip(['course_id', 'name', 'credits', 'course_type'], row)) for row in cursor.fetchall()]

        # Redirect to the same page after enrollment
        return render_template('student.html',
                               student=student,
                               earned_credits=earned_credits,
                               total_credits=total_credits,
                               current_courses=current_courses,
                               available_courses=available_courses,
                               enrollment_open=enrollment_open,
                               current_year=current_year,
                               current_semester=current_sem,
                               is_graduated=is_graduated,
                               progress=earned_credits,
                               required_credits=required_credits)


    # Render the dashboard template
    return render_template('student.html',
                           student=student,
                           earned_credits=earned_credits,
                           total_credits=total_credits,
                           current_courses=current_courses,
                           available_courses=available_courses,
                           enrollment_open=enrollment_open,
                           current_year=current_year,
                           current_semester=current_sem,
                           is_graduated=is_graduated,
                           progress=earned_credits,
                           required_credits=required_credits)

@app.route('/student/past_courses')
def past_courses():
    user_id = session.get('student_id')
    conn = get_db()
    cursor = conn.cursor()

    current_year, current_semester = get_current_session()

    # Fetch all past enrollments ordered chronologically
    cursor.execute("""
        SELECT 
            e.year, 
            e.semester, 
            e.course_id,
            e.grade,
            c.name,
            c.course_type,
            c.credits
        FROM Enrollments e
        JOIN Courses c ON e.course_id = c.course_id
        WHERE e.student_id = ? 
            AND (e.year < ? OR (e.year = ? AND e.semester < ?))
        ORDER BY e.year ASC, e.semester ASC
    """, (user_id, current_year, current_year, current_semester))
    rows = cursor.fetchall()

    # Group courses by semester for SPI
    semesters = defaultdict(list)
    for row in rows:
        year, semester, _, grade, name, course_type, credits = row
        semesters[(year, semester)].append({
            'name': name,
            'course_type': course_type,
            'credits': credits,
            'grade': grade
        })

    # Track latest attempts for CPI calculation
    latest_attempts = {}  # {course_id: (year, semester, grade, credits)}
    total_credits = 0
    total_weighted = 0
    results = []

    # Process semesters in chronological order
    for (year, semester) in sorted(semesters.keys()):
        # Get courses for this semester (for SPI)
        courses = semesters[(year, semester)]
        # Calculate SPI
        sem_credits = sum(c['credits'] for c in courses if c['grade'] is not None)
        sem_weighted = sum(c['credits'] * c['grade'] for c in courses if c['grade'] is not None)
        spi = round(sem_weighted / sem_credits, 2) if sem_credits else 0

        # Update CPI with latest attempts
        for course in courses:
            course_id = course['name']  # Assuming 'name' is unique; use course_id if available
            current_grade = course['grade']
            current_credits = course['credits']

            # Check if this is the latest attempt up to this semester
            existing = latest_attempts.get(course_id)
            if not existing or (year, semester) >= (existing['year'], existing['semester']):
                # Remove old contribution if exists
                if existing:
                    total_credits -= existing['credits']
                    total_weighted -= existing['credits'] * existing['grade']
                # Add new contribution
                if current_grade is not None:
                    total_credits += current_credits
                    total_weighted += current_credits * current_grade
                # Update latest attempt
                latest_attempts[course_id] = {
                    'year': year,
                    'semester': semester,
                    'grade': current_grade,
                    'credits': current_credits
                }

        # Calculate CPI up to this semester
        cpi = round(total_weighted / total_credits, 2) if total_credits else 0

        results.append({
            'year': year,
            'semester': semester,
            'courses': courses,
            'spi': spi,
            'cpi': cpi
        })

    return render_template('past_courses.html', results=results)


@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    year, semester = get_current_session()

    # Get all students and optionally filter by batch year
    selected_year = None
    if request.method == 'POST':
        selected_year = request.form.get('batch_filter')
        selected_type = request.form.get('course_filter')
    else:
        selected_type = None

    student_query = 'SELECT * FROM Students'
    course_query = 'SELECT * FROM Courses'
    student_params = []
    course_params = []

    if selected_year:
        student_query += ' WHERE batch_id = ?'
        student_params.append(selected_year)

    if selected_type:
        course_query += ' WHERE course_type = ?'
        course_params.append(selected_type)

    students = db.execute(student_query + ' ORDER BY student_id', student_params).fetchall()
    courses = db.execute(course_query + ' ORDER BY course_id', course_params).fetchall()
    batch_years = db.execute('SELECT DISTINCT batch_year FROM Batches').fetchall()
    is_enrollment_open=get_enrollment_status()

    total_enrollments = db.execute(
        'SELECT COUNT(*) as cnt FROM Enrollments WHERE year = ? AND semester = ?',
        (year, semester)
    ).fetchone()['cnt']


    return render_template('admin.html',
                           students=students,
                           courses=courses,
                           batch_years=batch_years,
                           selected_year=selected_year or "",
                           selected_type=selected_type or "",
                           year=year,
                           semester=semester,
                           is_enrollment_open=is_enrollment_open,
                           total_enrollments=total_enrollments)

@app.route('/admin/open-enrollment', methods=['POST'])
def open_enrollment():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    year, semester = get_current_session()
    db = get_db()
    db.execute('REPLACE INTO EnrollmentStatus (year, semester, is_enrollment_open) VALUES (?, ?, ?)', (year, semester, True))
    db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/close-enrollment', methods=['POST'])
def close_enrollment():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    year, semester = get_current_session()
    db = get_db()
    db.execute('REPLACE INTO EnrollmentStatus (year, semester, is_enrollment_open) VALUES (?, ?, ?)', (year, semester, False))
    db.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/upload_batch', methods=['GET', 'POST'])
def upload_batch():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    year, semester = get_current_session()  # Get current academic year

    if semester != 1:
        return render_template('upload_batch.html', year=year, error="New batches can only be uploaded in Semester 1.")

    # ✅ Check if batch already exists
    batch_exists = db.execute('SELECT * FROM Batches WHERE batch_year = ?', (year,)).fetchone()
    if batch_exists:
        return render_template('upload_batch.html', year=year, error="Batch for this year has already been uploaded.")

    if request.method == 'POST':
        student_names = request.form.getlist('student_names')
        student_names = [name.strip().title() for name in student_names]  # 👈 Normalize names
        student_names.sort()

        # Add batch if not already added
        batch = db.execute('SELECT * FROM Batches WHERE batch_year = ?', (year,)).fetchone()
        if not batch:
            db.execute('INSERT INTO Batches (batch_id, batch_year) VALUES (?, ?)', (year, year))
            db.commit()

        # Get last student_id used for the year prefix
        prefix = str(year)[-2:]  # e.g., "24" for 2024
        last_student = db.execute(
            "SELECT student_id FROM Students WHERE student_id LIKE ? ORDER BY student_id DESC LIMIT 1",
            (f"{prefix}%",)
        ).fetchone()

        if last_student:
            last_id_num = int(str(last_student['student_id'])[2:])
        else:
            last_id_num = 0

        # Insert new students
        for i, name in enumerate(student_names):
            new_id = int(f"{prefix}{last_id_num + i + 1:04d}")
            db.execute('INSERT INTO Students (student_id, name, batch_id) VALUES (?, ?, ?)', (new_id, name, year))

        db.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('upload_batch.html', year=year)

@app.route('/admin/upload-course', methods=['POST'])
def upload_course():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))


    name = request.form['name']
    credits = request.form['credits']
    course_type = request.form['course_type']
    db = get_db()
    existing = db.execute('SELECT * FROM Courses WHERE LOWER(name) = LOWER(?)', (name,)).fetchone()
    if existing:
        students = db.execute('SELECT * FROM Students').fetchall()
        batch_years = db.execute('SELECT DISTINCT batch_year FROM Batches').fetchall()
        courses = db.execute('SELECT * FROM Courses').fetchall()
        year, semester = get_current_session()
        is_enrollment_open=get_enrollment_status()
        return render_template(
            'admin.html',
            students=students,
            batch_years=batch_years,
            courses=courses,   # 👈 Don't forget this
            year=year,
            semester=semester,
            is_enrollment_open=is_enrollment_open,
            error=f"Course '{name}' already exists."
        )
    db.execute('INSERT INTO Courses (name, credits, course_type) VALUES (?, ?, ?)', (name, credits, course_type))
    db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_enrollment', methods=['POST'])
def toggle_enrollment():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    year, semester = get_current_session()
    action = request.form.get('action')

    is_enrollment_open = 1 if action == 'open' else 0

    db.execute('''
        INSERT INTO EnrollmentStatus (year, semester, is_enrollment_open)
        VALUES (?, ?, ?)
        ON CONFLICT(year, semester) DO UPDATE SET is_enrollment_open=excluded.is_enrollment_open
    ''', (year, semester, is_enrollment_open))
    db.commit()

    flash(f"Enrollment {'opened' if is_enrollment_open else 'closed'} for Year {year}, Semester {semester}.", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload-grades', methods=['GET', 'POST'])
def upload_grades():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    year, semester = get_current_session()

    # 🔒 Prevent upload if enrollment is still open
    status = db.execute('''
        SELECT is_enrollment_open FROM EnrollmentStatus
        WHERE year = ? AND semester = ?
    ''', (year, semester)).fetchone()

    if status and status['is_enrollment_open']:
        flash("Please close enrollment before uploading grades.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        enrollment_val = request.form.get('enrollment')
        grade = float(request.form.get('grade'))

        if not enrollment_val:
            flash("Enrollment selection is missing.", "error")
            return redirect(url_for('upload_grades'))

        try:
            student_id, course_id = enrollment_val.split('|')
        except ValueError:
            flash("Invalid enrollment data.", "error")
            return redirect(url_for('upload_grades'))


        # ✅ Ensure enrollment exists
        existing = db.execute('''
            SELECT * FROM Enrollments
            WHERE student_id = ? AND course_id = ? AND year = ? AND semester = ?
        ''', (student_id, course_id, year, semester)).fetchone()

        if not existing:
            db.execute('''
                INSERT INTO Enrollments (student_id, course_id, year, semester, grade)
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, course_id, year, semester, grade))
        else:
            db.execute('''
                UPDATE Enrollments
                SET grade = ?
                WHERE student_id = ? AND course_id = ? AND year = ? AND semester = ?
            ''', (grade, student_id, course_id, year, semester))

        db.commit()

        # ✅ Check if all grades are submitted
        total_enrollments = db.execute('''
            SELECT COUNT(*) as cnt
            FROM Enrollments
            WHERE year = ? AND semester = ?
        ''', (year, semester)).fetchone()['cnt']

        if total_enrollments == 0:
            all_grades_submitted = True
        else:
            incomplete = db.execute('''
                SELECT COUNT(*) as cnt
                FROM Enrollments
                WHERE year = ? AND semester = ? AND grade IS NULL
            ''', (year, semester)).fetchone()['cnt']
            all_grades_submitted = (incomplete == 0)

        if all_grades_submitted:
            # Advance semester
            if semester == 1:
                new_year = year
                new_semester = 2
            else:
                new_year = year + 1
                new_semester = 1

            # Update session
            db.execute('UPDATE Session SET year = ?, semester = ? WHERE id = 1',
                       (new_year, new_semester))

            # ✅ Automatically open enrollment for new semester
            db.execute('''
                INSERT INTO EnrollmentStatus (year, semester, is_enrollment_open)
                VALUES (?, ?, 1)
                ON CONFLICT(year, semester) DO UPDATE SET is_enrollment_open=1
            ''', (new_year, new_semester))

            db.commit()
            flash(f"Grades uploaded. Semester advanced to Year {new_year}, Semester {new_semester}. Enrollment is now open.", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Grade submitted successfully.", "success")

    # GET: Render the grade upload page
    # Students who are enrolled in the current year and semester AND whose grades are still NULL
    pending_grades = db.execute('''
        SELECT s.student_id, s.name, c.course_id, c.name AS course_name
        FROM Enrollments e
        JOIN Students s ON e.student_id = s.student_id
        JOIN Courses c ON e.course_id = c.course_id
        WHERE e.year = ? AND e.semester = ? AND e.grade IS NULL
    ''', (year, semester)).fetchall()

    return render_template('upload_grades.html', pending_grades=pending_grades, year=year, semester=semester)

@app.route('/admin/force-advance', methods=['POST'])
def force_advance():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    year, semester = get_current_session()
    db = get_db()

    # Advance semester
    if semester == 1:
        new_year = year
        new_semester = 2
    else:
        new_year = year + 1
        new_semester = 1

    # Update session
    db.execute('UPDATE Session SET year = ?, semester = ? WHERE id = 1',
               (new_year, new_semester))

    # Automatically open enrollment for new semester
    db.execute('''
        INSERT INTO EnrollmentStatus (year, semester, is_enrollment_open)
        VALUES (?, ?, 1)
        ON CONFLICT(year, semester) DO UPDATE SET is_enrollment_open=1
    ''', (new_year, new_semester))

    db.commit()
    flash(f"Semester advanced to Year {new_year}, Semester {new_semester}.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80,threaded=True,debug=True)