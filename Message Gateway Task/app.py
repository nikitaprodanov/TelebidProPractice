from flask import Flask
from flask import render_template, url_for, redirect, request
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256

app = Flask(__name__)

ENV = 'dev'

if ENV == 'dev':
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://zyqszqzwkdibfy:3903e3cbb3bb12c6cd6b1b1df76c206064b5a7dc6ee16d1642998aca60665114@ec2-52-0-155-79.compute-1.amazonaws.com:5432/d95t75v835sdmb'
    debug = True
elif ENV == 'prod':
    app.config['SQLALCHEMY_DATABASE_URI'] = ''
    debug = False

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
            return redirect(url_for('register_error'))

        else:
            data = User(username=username, password=password, email=email, phone=phone, hasWhatsapp=hasWhatsapp)
            db.session.add(data)
            db.session.commit()
            return redirect(url_for('index'))

@app.route('/register/error')
def register_error():
    return render_template('confirm_password_error.html')

if __name__ == '__main__':
    app.run(debug=debug)