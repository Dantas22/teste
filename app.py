from flask import Flask, render_template, request, redirect, session, flash, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SECRET_KEY'] = 'secret'
db = SQLAlchemy(app)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    publisher = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    total_quantity = db.Column(db.Integer, nullable=False)
    available_quantity = db.Column(db.Integer, nullable=False)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    pending_books = db.relationship('Book', secondary='loan', backref=db.backref('students', lazy='dynamic'),
                                    secondaryjoin='Loan.student_id == Student.id')

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class Loan(db.Model):
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    loan_date = db.Column(db.Date, nullable=False)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/books/add', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        publisher = request.form['publisher']
        year = int(request.form['year'])
        total_quantity = int(request.form['total_quantity'])
        available_quantity = total_quantity

        book = Book(
            title=title,
            publisher=publisher,
            year=year,
            total_quantity=total_quantity,
            available_quantity=available_quantity
        )
        db.session.add(book)
        db.session.commit()
        return redirect('/')
    return render_template('add_book.html')


@app.route('/students/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        student = Student(name=name)
        student.set_password(password)

        db.session.add(student)
        db.session.commit()
        return redirect('/')
    return render_template('add_student.html')


@app.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        employee = Employee(name=name)
        employee.set_password(password)

        db.session.add(employee)
        db.session.commit()
        return redirect('/')
    return render_template('add_employee.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        student = Student.query.filter_by(name=username).first()
        employee = Employee.query.filter_by(name=username).first()

        if student and student.check_password(password):
            session['user_id'] = student.id
            session['user_type'] = 'student'
            return redirect('/')

        if employee and employee.check_password(password):
            session['user_id'] = employee.id
            session['user_type'] = 'employee'
            return redirect('/')

        flash('Usuário ou senha incorretos.', 'error')
        return redirect('/login')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_type', None)
    return redirect('/')


@app.route('/loan', methods=['GET', 'POST'])
def loan_book():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return redirect('/login')

    if request.method == 'POST':
        student_id = int(request.form['student_id'])
        book_id = int(request.form['book_id'])

        student = Student.query.get(student_id)
        if not student:
            return "Aluno não encontrado."

        book = Book.query.filter_by(id=book_id).filter(Book.available_quantity > 0).first()
        if not book:
            return "Livro não encontrado ou indisponível."

        if len(student.pending_books) >= 3:
            return "O aluno já possui 3 livros alocados."

        loan = Loan(book_id=book.id, student_id=student.id, employee_id=session['user_id'], loan_date=date.today())
        db.session.add(loan)
        book.available_quantity -= 1
        db.session.commit()

        flash('Livro emprestado com sucesso', 'success')
        return redirect('/loan')

    students = Student.query.all()
    books = Book.query.filter(Book.available_quantity > 0).all()
    return render_template('loan_book.html', students=students, books=books, messages=get_flashed_messages())


@app.route('/return', methods=['GET', 'POST'])
def return_book():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return redirect('/login')

    if request.method == 'POST':
        student_id = int(request.form['student_id'])
        book_id = int(request.form['book_id'])

        student = Student.query.get(student_id)
        if not student:
            return "Aluno não encontrado."

        book = Book.query.filter_by(id=book_id).first()
        if not book or book not in student.pending_books:
            return "Livro não alocado para o aluno."

        loan = Loan.query.filter_by(book_id=book.id, student_id=student.id).first()
        db.session.delete(loan)
        book.available_quantity += 1
        db.session.commit()

        flash('Livro devolvido com sucesso', 'success')
        return redirect('/return')

    students = Student.query.all()
    books = Book.query.filter(Book.available_quantity < Book.total_quantity).all()
    return render_template('return_book.html', students=students, books=books, messages=get_flashed_messages())


@app.route('/report', methods=['GET', 'POST'])
def generate_report():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return redirect('/login')

    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        loans = Loan.query.filter(Loan.loan_date.between(start_date, end_date)).all()

        return render_template('report.html', loans=loans)

    return render_template('generate_report.html')


@app.route('/users')
def users_table():
    students = Student.query.all()
    employees = Employee.query.all()
    return render_template('users_table.html', students=students, employees=employees)



@app.route('/lista_livros')
def lista_livros():
    book = Book.query.all()
    
    return render_template('lista_livros.html', book = book)










if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
