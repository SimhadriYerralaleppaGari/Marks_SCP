# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import logout_user
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///grades.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    semesters = db.relationship('Semester', backref='user', lazy=True)

class Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    sgpa = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subjects = db.relationship('Subject', backref='semester', lazy=True, cascade="all, delete")

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(2))
    marks = db.Column(db.Float)
    grade_point = db.Column(db.Float)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Grade conversion dictionaries
GRADE_TO_POINT = {
    'S': 10.0, 'A1': 9.5, 'A2': 9.0, 'A3': 8.5,
    'B1': 8.0,'B2': 7.5, 'C1': 7.0, 'C2': 6.5, 'D1': 6.0,
    'D2': 5.5, 'F': 0.0, 'AB': 0.0
}

def marks_to_grade_point(marks):
    if marks >= 95: return 10.0
    elif 90 <= marks < 95: return 9.5
    elif 85 <= marks < 90: return 9.0
    elif 80 <= marks < 85: return 8.5
    elif 75 <= marks < 80: return 8.0
    elif 70 <= marks < 75: return 7.5
    elif 65 <= marks < 70: return 7.0
    elif 60 <= marks < 65: return 6.5
    elif 55 <= marks < 60: return 6.0
    elif 50 <= marks < 55: return 5.5
    else: return 0.0

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('signup'))
            
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('signup'))
            
        # Create new user
        user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
        
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    semesters = Semester.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', semesters=semesters)

@app.route('/add_semester', methods=['GET', 'POST'])
@login_required
def add_semester():
    if request.method == 'POST':
        semester_name = request.form['semester_name']
        num_subjects = int(request.form['num_subjects'])
        semester = Semester(name=semester_name, user_id=current_user.id)
        db.session.add(semester)
        db.session.commit()
        return redirect(url_for('add_subjects', semester_id=semester.id, num_subjects=num_subjects))
    return render_template('add_semester.html')

@app.route('/add_subjects/<int:semester_id>/<int:num_subjects>', methods=['GET', 'POST'])
@login_required
def add_subjects(semester_id, num_subjects):
    if request.method == 'POST':
        total_credits = 0
        total_weighted_points = 0
        
        for i in range(num_subjects):
            credits = int(request.form[f'credits_{i}'])
            input_type = request.form[f'input_type_{i}']
            
            if input_type == 'grade':
                grade = request.form[f'grade_{i}'].upper()
                grade_point = GRADE_TO_POINT[grade]
                subject = Subject(
                    name=f'Subject {i+1}',
                    credits=credits,
                    grade=grade,
                    grade_point=grade_point,
                    semester_id=semester_id
                )
            else:
                marks = float(request.form[f'marks_{i}'])
                grade_point = marks_to_grade_point(marks)
                subject = Subject(
                    name=f'Subject {i+1}',
                    credits=credits,
                    marks=marks,
                    grade_point=grade_point,
                    semester_id=semester_id
                )
            
            db.session.add(subject)
            total_credits += credits
            total_weighted_points += credits * grade_point
        
        sgpa = total_weighted_points / total_credits
        semester = Semester.query.get(semester_id)
        semester.sgpa = round(sgpa, 2)
        db.session.commit()
        
        return redirect(url_for('view_results', semester_id=semester_id))
    return render_template('add_subjects.html', num_subjects=num_subjects)

@app.route('/view_results/<int:semester_id>')
@login_required
def view_results(semester_id):
    semester = Semester.query.get_or_404(semester_id)
    return render_template('view_results.html', semester=semester)

@app.route('/calculate_cgpa')
@login_required
def calculate_cgpa():
    semesters = Semester.query.filter_by(user_id=current_user.id).all()
    if not semesters:
        flash('No semesters found')
        return redirect(url_for('dashboard'))
    
    total_sgpa = sum(semester.sgpa for semester in semesters)
    cgpa = total_sgpa / len(semesters)
    percentage = cgpa * 10
    
    return render_template('cgpa_results.html', 
                         semesters=semesters,
                         cgpa=round(cgpa, 2),
                         percentage=round(percentage, 2))

# Add these updated routes to your app.py

@app.route('/edit_semester/<int:semester_id>', methods=['GET', 'POST'])
@login_required
def edit_semester(semester_id):
    semester = Semester.query.get_or_404(semester_id)
    if request.method == 'POST':
        semester.name = request.form['semester_name']
        
        # Update existing subjects
        for subject in semester.subjects:
            subject_id = str(subject.id)
            if subject_id in request.form:  # Check if subject still exists in form
                credits = int(request.form[f'credits_{subject_id}'])
                input_type = request.form[f'input_type_{subject_id}']
                
                if input_type == 'grade':
                    grade = request.form[f'grade_{subject_id}'].upper()
                    grade_point = GRADE_TO_POINT[grade]
                    subject.grade = grade
                    subject.marks = None
                else:
                    marks = float(request.form[f'marks_{subject_id}'])
                    grade_point = marks_to_grade_point(marks)
                    subject.grade = None
                    subject.marks = marks
                
                subject.credits = credits
                subject.grade_point = grade_point
            else:  # Subject was removed
                db.session.delete(subject)
        
        # Add new subjects if any
        new_subjects_count = int(request.form.get('new_subjects_count', 0))
        for i in range(new_subjects_count):
            credits = int(request.form[f'new_credits_{i}'])
            input_type = request.form[f'new_input_type_{i}']
            
            if input_type == 'grade':
                grade = request.form[f'new_grade_{i}'].upper()
                grade_point = GRADE_TO_POINT[grade]
                subject = Subject(
                    name=f'Subject {len(semester.subjects) + i + 1}',
                    credits=credits,
                    grade=grade,
                    grade_point=grade_point,
                    semester_id=semester_id
                )
            else:
                marks = float(request.form[f'new_marks_{i}'])
                grade_point = marks_to_grade_point(marks)
                subject = Subject(
                    name=f'Subject {len(semester.subjects) + i + 1}',
                    credits=credits,
                    marks=marks,
                    grade_point=grade_point,
                    semester_id=semester_id
                )
            db.session.add(subject)
        
        # Recalculate SGPA
        total_credits = 0
        total_weighted_points = 0
        
        for subject in semester.subjects:
            total_credits += subject.credits
            total_weighted_points += subject.credits * subject.grade_point
        
        semester.sgpa = round(total_weighted_points / total_credits, 2)
        
        db.session.commit()
        flash('Semester updated successfully')
        return redirect(url_for('dashboard'))
        
    return render_template('edit_semester.html', semester=semester)

@app.route('/delete_semester/<int:semester_id>')
@login_required
def delete_semester(semester_id):
    semester = Semester.query.get_or_404(semester_id)
    db.session.delete(semester)
    db.session.commit()
    flash('Semester deleted successfully')
    return redirect(url_for('dashboard'))

# Add this route to your app.py
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)