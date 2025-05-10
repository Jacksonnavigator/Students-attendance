from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)
app.secret_key = "studentattendancesystem"
app.jinja_env.globals.update(now=datetime.now)

# Database initialization
def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Create students table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        student_name TEXT PRIMARY KEY
    )
    ''')
    
    # Create attendance_records table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT,
        timestamp TEXT,
        FOREIGN KEY (student_name) REFERENCES students (student_name)
    )
    ''')
    
    # Create attendance_window table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance_window (
        is_open INTEGER DEFAULT 0,
        opened_at TEXT,
        closes_at TEXT
    )
    ''')
    
    # Check if attendance_window has any rows
    cursor.execute('SELECT COUNT(*) FROM attendance_window')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO attendance_window (is_open, opened_at, closes_at) VALUES (0, NULL, NULL)')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Helper function to check if attendance window is open
def is_attendance_window_open():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_open, closes_at FROM attendance_window')
    result = cursor.fetchone()
    conn.close()
    
    if result[0] == 1:
        closes_at = datetime.strptime(result[1], '%Y-%m-%d %H:%M:%S')
        if closes_at > datetime.now():
            return True
    return False

# Helper function to check if student has already marked attendance today
def has_marked_attendance_today(student_name):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute(
        'SELECT COUNT(*) FROM attendance_records WHERE student_name = ? AND date(timestamp) = ?', 
        (student_name, today)
    )
    result = cursor.fetchone()[0] > 0
    conn.close()
    return result

# Student login route
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_name = request.form['student_name'].strip()
        if not student_name:
            flash('Please enter your name')
            return redirect(url_for('login'))
        
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        
        # Check if student exists, if not register them
        cursor.execute('SELECT student_name FROM students WHERE student_name = ?', (student_name,))
        if cursor.fetchone() is None:
            cursor.execute('INSERT INTO students (student_name) VALUES (?)', (student_name,))
            conn.commit()
            flash(f'New student {student_name} registered!')
        
        conn.close()
        
        # Set session and redirect to attendance page
        session['student_name'] = student_name
        return redirect(url_for('attendance'))
    
    return render_template('login.html')

# Student attendance route
@app.route('/attendance')
def attendance():
    if 'student_name' not in session:
        return redirect(url_for('login'))
    
    student_name = session['student_name']
    window_open = is_attendance_window_open()
    already_marked = has_marked_attendance_today(student_name)
    
    return render_template('attendance.html', 
                          student_name=student_name,
                          window_open=window_open,
                          already_marked=already_marked)

# Mark attendance route
@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    if 'student_name' not in session:
        return redirect(url_for('login'))
    
    student_name = session['student_name']
    
    # Check if window is open and attendance not already marked
    if not is_attendance_window_open():
        flash('Attendance window is closed')
        return redirect(url_for('attendance'))
    
    if has_marked_attendance_today(student_name):
        flash('You have already marked your attendance today')
        return redirect(url_for('attendance'))
    
    # Mark attendance
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'INSERT INTO attendance_records (student_name, timestamp) VALUES (?, ?)',
        (student_name, current_time)
    )
    conn.commit()
    conn.close()
    
    flash('Attendance marked successfully!')
    return redirect(url_for('attendance'))

# Student logout route
@app.route('/logout')
def logout():
    session.pop('student_name', None)
    session.pop('is_teacher', None)
    return redirect(url_for('login'))

# Teacher login route
@app.route('/teacher', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        password = request.form['password']
        
        # Simple password check (in a real app, use proper authentication)
        if password == 'admin123':
            session['is_teacher'] = True
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Incorrect password')
            
    return render_template('teacher_login.html')

# Teacher dashboard route
@app.route('/teacher/dashboard')
def teacher_dashboard():
    if not session.get('is_teacher'):
        return redirect(url_for('teacher_login'))
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Get all students
    cursor.execute('SELECT student_name FROM students')
    students = [row[0] for row in cursor.fetchall()]
    
    # Get today's attendance
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute(
        'SELECT DISTINCT student_name FROM attendance_records WHERE date(timestamp) = ?',
        (today,)
    )
    present_students = [row[0] for row in cursor.fetchall()]
    
    # Get attendance window status
    cursor.execute('SELECT is_open, opened_at, closes_at FROM attendance_window')
    window_status = cursor.fetchone()
    is_open = window_status[0] == 1
    
    # Format window times for display
    opened_at = window_status[1]
    closes_at = window_status[2]
    if opened_at:
        opened_at = datetime.strptime(opened_at, '%Y-%m-%d %H:%M:%S').strftime('%I:%M %p')
    if closes_at:
        closes_at = datetime.strptime(closes_at, '%Y-%m-%d %H:%M:%S').strftime('%I:%M %p')
    
    conn.close()
    
    return render_template('teacher_dashboard.html',
                          students=students,
                          present_students=present_students,
                          is_open=is_open,
                          opened_at=opened_at,
                          closes_at=closes_at)

# Add student route
@app.route('/teacher/add_student', methods=['POST'])
def add_student():
    if not session.get('is_teacher'):
        return redirect(url_for('teacher_login'))
    
    student_name = request.form['student_name'].strip()
    if not student_name:
        flash('Please enter a student name')
        return redirect(url_for('teacher_dashboard'))
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Check if student already exists
    cursor.execute('SELECT student_name FROM students WHERE student_name = ?', (student_name,))
    if cursor.fetchone() is not None:
        flash(f'Student {student_name} already exists')
    else:
        cursor.execute('INSERT INTO students (student_name) VALUES (?)', (student_name,))
        conn.commit()
        flash(f'Student {student_name} added successfully')
    
    conn.close()
    return redirect(url_for('teacher_dashboard'))

# Open attendance window route
@app.route('/teacher/open_window', methods=['POST'])
def open_window():
    if not session.get('is_teacher'):
        return redirect(url_for('teacher_login'))
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Open window for 10 minutes
    opened_at = datetime.now()
    closes_at = opened_at + timedelta(minutes=10)
    
    cursor.execute(
        'UPDATE attendance_window SET is_open = 1, opened_at = ?, closes_at = ?',
        (opened_at.strftime('%Y-%m-%d %H:%M:%S'), closes_at.strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()
    
    flash('Attendance window opened for 10 minutes')
    return redirect(url_for('teacher_dashboard'))

# Close attendance window route
@app.route('/teacher/close_window', methods=['POST'])
def close_window():
    if not session.get('is_teacher'):
        return redirect(url_for('teacher_login'))
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE attendance_window SET is_open = 0')
    conn.commit()
    conn.close()
    
    flash('Attendance window closed')
    return redirect(url_for('teacher_dashboard'))

# Monthly report route
@app.route('/teacher/report')
def teacher_report():
    if not session.get('is_teacher'):
        return redirect(url_for('teacher_login'))
    
    # Get previous month
    today = datetime.now()
    first_day_prev_month = today.replace(day=1) - timedelta(days=1)
    prev_month = first_day_prev_month.month
    prev_month_year = first_day_prev_month.year
    
    # Calculate start and end dates
    start_date = datetime(prev_month_year, prev_month, 1)
    last_day = calendar.monthrange(prev_month_year, prev_month)[1]
    end_date = datetime(prev_month_year, prev_month, last_day)
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Get all students
    cursor.execute('SELECT student_name FROM students')
    students = [row[0] for row in cursor.fetchall()]
    
    # Get attendance for each student in the previous month
    attendance_data = []
    for student in students:
        cursor.execute('''
            SELECT COUNT(DISTINCT date(timestamp)) 
            FROM attendance_records 
            WHERE student_name = ? AND 
                  timestamp BETWEEN ? AND ?
        ''', (student, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d 23:59:59')))
        days_present = cursor.fetchone()[0]
        attendance_data.append({
            'name': student,
            'days_present': days_present,
            'total_days': last_day,
            'percentage': round((days_present / last_day) * 100, 1) if last_day > 0 else 0
        })
    
    conn.close()
    
    month_name = start_date.strftime('%B %Y')
    
    return render_template('teacher_report.html', 
                          attendance_data=attendance_data,
                          month_name=month_name)

if __name__ == '__main__':
    # This allows the app to be run locally or in production
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port, debug=False)
