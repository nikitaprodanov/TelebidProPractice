from flask import Flask
from flask import render_template, url_for, redirect, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from functools import wraps
from datetime import datetime

# Initialize app
app = Flask(__name__)

# Environment configurations
ENV = 'dev'

if ENV == 'dev':
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://zyqszqzwkdibfy:3903e3cbb3bb12c6cd6b1b1df76c206064b5a7dc6ee16d1642998aca60665114@ec2-52-0-155-79.compute-1.amazonaws.com:5432/d95t75v835sdmb'
    app.config['SECRET_KEY'] = 'some secret'
    debug = True
elif ENV == 'prod':
    app.config['SQLALCHEMY_DATABASE_URI'] = ''
    app.config['SECRET_KEY'] = ''
    debug = False

# General configurations
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

s = URLSafeTimedSerializer('SECRET_KEY')

app.config.from_pyfile('configuration.cfg')

mail = Mail(app)

# Database models
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text())
    password = db.Column(db.Text())
    email = db.Column(db.Text())
    phone = db.Column(db.Text())
    hasWhatsapp = db.Column(db.Boolean())
    verified = db.Column(db.Boolean())
    messages = db.relationship('Message', backref='sender')

    def __init__(self, username, password, email, phone, hasWhatsapp):
        self.username = username
        self.password = password
        self.email = email
        self.phone = phone
        self.hasWhatsapp = hasWhatsapp
        self.verified = False

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    senderId = db.Column(db.Integer(), db.ForeignKey('users.id'))
    reciever = db.Column(db.Text())
    message = db.Column(db.Text())
    sendDate = db.Column(db.DateTime, default=datetime.utcnow)
    tax = db.Column(db.Integer())
    status = db.Column(db.Text())

    def __init__(self, reciever, message, tax, status, sender):
        self.reciever = reciever
        self.message = message
        self.tax = tax
        self.status = status
        self.sender = sender
        

@app.route('/')
def index():
    return render_template('land_page.html')

# REGISTER AND VERIFICATION ROUTES AND ERROR HANDLERS

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    if request.method == 'POST':
        username = request.form['username']
        password = pbkdf2_sha256.hash(request.form['password'])
        email = request.form['email']
        phone = request.form['phone-number']
        hasWhatsappRes = request.form.get('has-whatsapp')
        hasWhatsapp = False if hasWhatsappRes == None else True

        if not pbkdf2_sha256.verify(request.form['confirm-pswd'], password):
            return redirect(url_for('confirm_password_error'))
        if User.query.filter_by(email=email).count() > 0:
            return redirect(url_for('register_email_error'))
        else:
            data = User(username=username, password=password, email=email, phone=phone, hasWhatsapp=hasWhatsapp)
            db.session.add(data)
            db.session.commit()

            token = s.dumps(email, salt='email-confirm')

            msg = Message('Confirmation Email', sender='nikitaprodanov@gmail.com', recipients=[email])
            link = url_for('confirm_email', token=token, _external=True)
            msg.body = "To confirm your email please click the link: {}. If you didn't expect a verification link please ignore this email.".format(link)
            mail.send(msg)

            return redirect(url_for('check_email', email=email))

@app.route('/verification/send_again', methods=['GET', 'POST'])
def verification_send():
    if request.method == 'GET':
        return render_template('send_mail_again.html')
    if request.method == 'POST':
        email = request.form['email']
        token = s.dumps(email, salt='email-confirm')

        msg = Message('Confirmation Email', sender='nikitaprodanov@gmail.com', recipients=[email])
        link = url_for('confirm_email', token=token, _external=True)
        msg.body = "To confirm your email please click the link: {}. If you didn't expect a verification link please ignore this email.".format(link)
        mail.send(msg)

        return redirect(url_for('check_email', email=email))

@app.route('/register/confirm_error')
def confirm_password_error():
    return render_template('confirm_password_error.html')

@app.route('/register/email_error')
def register_email_error():
    return render_template('register_email_error.html')

@app.route('/check_email/<email>')
def check_email(email):
    return render_template('sent_verification.html', email=email)

@app.route('/confirm_email/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=50)
        user = User.query.filter_by(email=email).first()
        user.verified = True
        session['verified'] = True
        db.session.commit()
        return redirect(url_for('index'))
    except SignatureExpired:
        return redirect(url_for('token_error_expired'))
    except BadTimeSignature:
        return redirect(url_for('token_error_spelling'))

@app.route('/token_error/expired')
def token_error_expired():
    return render_template('token_error_expired.html')

@app.route('/token_error/misspelled')
def token_error_spelling():
    return render_template('token_error_misspelled.html')

# LOGIN ROUTES AND METHODS

def require_login(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return func(*args, **kwargs)
    return wrapper

def require_verification(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('verified'):
            return redirect('/verification/send_again')
        return func(*args, **kwargs)
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    if request.method == 'POST':
        email = request.form['email']
        print(request.form['password'])
        user = User.query.filter_by(email=email).first()
        if user is None:
            return redirect(url_for('wrong_credentials_error'))
        if not pbkdf2_sha256.verify(request.form['password'], user.password):
            return redirect(url_for('wrong_credentials_error'))
        # TODO: finish implementation when all credentials are good
        session['logged_in'] = True
        session['user_id'] = user.id
        session['verified'] = user.verified
        return redirect(url_for('home'))

@app.route('/logout')
@require_login
def logout():
    session['logged_in'] = False
    session['user_id'] = None
    session['verified'] = False
    return redirect('/')

@app.route('/login/credentials_error')
def wrong_credentials_error():
    return render_template('wrong_credentials.html')

# REQUIRED LOGIN AND MAIL VERIFICATION METHODS
@app.route('/home')
@require_login
def home():
    user = User.query.filter_by(id=session.get('user_id')).first()
    return render_template('home.html', user=user)

@app.route('/send_sms', methods=['GET', 'POST'])
@require_login
@require_verification
def send_sms():
    if request.method == 'GET':
        return render_template('send_sms.html')
    if request.method == 'POST':
        reciever = request.form['phone-number']
        msg = "This is automated sms from {}: {}".format(request.form['from'], request.form['message'])
        tax = 5
        status = 'develop' # TODO: change to actual status when implementing the twilio api
        sender = User.query.filter_by(id=session.get('user_id')).first()

        data = Message(reciever=reciever, message=msg, tax=tax, status=status, sender=sender)
        db.session.add(data)
        db.session.commit()
        return redirect(url_for('success_sms'))

@app.route('/send_sms/sucsess')
@require_login
@require_verification
def success_sms():
    return render_template('success_sms.html')
    
@app.route('/user/sent_sms')
@require_login
@require_verification
def sent_sms():
    user = User.query.filter_by(id=session.get('user_id')).first()
    messages = user.messages
    return render_template('sent_sms_list.html', messages=messages, user=user)

if __name__ == '__main__':
    app.run(debug=debug)