from flask import Flask
from flask import render_template, url_for, redirect, request, flash
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature

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

# app.config['MAIL_SERVER']='smtp.gmail.com'
# app.config['MAIL_USERNAME']='nikitaprodanov20@gmail.com'
# app.config['MAIL_PASSWORD']='nikita0708'
# app.config['MAIL_PORT']=465
# app.config['MAIL_USE_SSL']=True
# app.config['MAIL_USE_TLS']=False

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

    def __init__(self, username, password, email, phone, hasWhatsapp):
        self.username = username
        self.password = pbkdf2_sha256.hash(password)
        self.email = email
        self.phone = phone
        self.hasWhatsapp = hasWhatsapp
        self.verified = False

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
        elif User.query.filter_by(email=email).count() > 0:
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

if __name__ == '__main__':
    app.run(debug=debug)