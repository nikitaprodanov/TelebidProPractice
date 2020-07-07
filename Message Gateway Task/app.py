from flask import Flask
from flask import render_template, url_for, redirect, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from functools import wraps
from datetime import datetime
from twilio.rest import Client
import paypalrestsdk
import json
import random
import string

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
s = URLSafeTimedSerializer('SECRET_KEY')

app.config.from_pyfile('configuration.cfg')

mail = Mail(app)

paypalrestsdk.configure({
  "mode": "sandbox", # sandbox or live
  "client_id": "AfxkPJLHBYNgbp6qAUuNdtuORQS2pbtci_RyoU0OWSgv7r56pYvOKWaVVQWeBz_zWD2W4wYcTnNgvmgL",
  "client_secret": "EJzlHUnA4eEG79116_Sk2BDVAFeFBbW_9sNtrUhAh7hG8RhezM0TQ0hXblfr32M5NPlZUrPHaJvA-TaQ" })

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
    points = db.Column(db.Integer())
    messages = db.relationship('SMS', backref='sender')
    contacts = db.relationship('Contact', backref='owner')
    payments = db.relationship('Payment', backref='payer')

    def __init__(self, username, password, email, phone, hasWhatsapp):
        self.username = username
        self.password = password
        self.email = email
        self.phone = phone
        self.hasWhatsapp = hasWhatsapp
        self.verified = False
        self.points = 0

class SMS(db.Model):
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

class Contact(db.Model):
    __tablename__ = "contacts"
    id = db.Column(db.Integer, primary_key=True)
    ownerId = db.Column(db.Integer(), db.ForeignKey('users.id'))
    reciever = db.Column(db.Text())
    contactName = db.Column(db.Text())
    method = db.Column(db.Text())

    def __init__(self, reciever, contactName, method, owner):
        self.reciever = reciever
        self.contactName = contactName
        self.method = method
        self.owner = owner

class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    payerId = db.Column(db.Integer(), db.ForeignKey('users.id'))
    bill = db.Column(db.Integer())
    payDate = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Text())
    plan = db.Column(db.Text())

    def __init__(self, bill, status, plan, payer):
        self.bill = bill
        self.status = status
        self.plan = plan
        self.payer = payer
        

@app.route('/')
def index():
    if session.get('logged_in'):
        return redirect('/home')
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
            msg.html = render_template('email.html', link=link)
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
        msg.html = render_template('email.html', link=link)
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
        return redirect(url_for('home'))
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
        user = User.query.filter_by(email=email).first()
        if user is None:
            return redirect(url_for('wrong_credentials_error'))
        if not pbkdf2_sha256.verify(request.form['password'], user.password):
            return redirect(url_for('wrong_credentials_error'))
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
        user = User.query.filter_by(id=session.get('user_id')).first()
        if user.points < app.config['SMS_TAX_POINTS']:
            return redirect(url_for('payment_form'))

        account_sid = "AC68d1456824929a8b36012db1c7df9cd6"
        auth_token = "87b90a5e8fc92f0a09ee154a1d867dbc"
        client = Client(account_sid, auth_token)

        try:
            reciever = request.form['phone-number']
            msg = "This is automated sms from {}: {}".format(request.form['from'], request.form['message'])
            tax = app.config['SMS_TAX_POINTS']
            sender = User.query.filter_by(id=session.get('user_id')).first()

            contact = Contact.query.filter_by(owner=sender, reciever=reciever, method='sms').first()

            if contact:
                reciever = contact.contactName
            
            data = SMS(reciever=reciever, message=msg, tax=tax, status='none', sender=sender)
            db.session.add(data)
            db.session.commit()

            callback_uri = url_for('change_status', id=data.id, _external=True)

            sms = client.messages.create(
                from_="+12018317102",
                body=msg,
                status_callback=str(callback_uri),
                to=request.form['phone-number']
            )

            sender.points -= tax
            db.session.commit()

            return redirect(url_for('success_sms'))
        except:
            return redirect(url_for('sms_error'))

@app.route('/messages/status/<int:id>', methods=['POST'])
def change_status(id):
    message = Message.query.filter_by(id=id).first()
    status = request.json.get("MessageStatus")
    message.status = status
    db.session.commit()
    return 'ok'

@app.route('/send_sms/error')
@require_login
@require_verification
def sms_error():
    return render_template('sms_error.html')

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

@app.route('/user/contacts')
@require_login
@require_verification
def user_contacts():
    user = User.query.filter_by(id=session.get('user_id')).first()
    contacts = user.contacts
    return render_template('user_contacts.html', contacts=contacts)

@app.route('/user/payments')
@require_login
@require_verification
def user_payments():
    user = User.query.filter_by(id=session.get('user_id')).first()
    payments = user.payments
    return render_template('user_payments.html', payments=payments)

@app.route('/send_sms_from_contacts/<reciever>/<method>')
@require_login
@require_verification
def send_sms_from_contacts(reciever, method):
    return render_template('send_from_contact.html', reciever=reciever)

@app.route('/new_contact', methods=['GET', 'POST'])
@require_login
@require_verification
def new_contact():
    if request.method == 'GET':
        return render_template('new_contact.html')
    if request.method == 'POST':
        reciever = request.form['phone-number']
        contactName = request.form['name']
        method = 'sms'
        user = User.query.filter_by(id=session.get('user_id')).first()
        data = Contact(reciever=reciever, contactName=contactName, method=method, owner=user)
        db.session.add(data)
        db.session.commit()
        return redirect('/user/contacts')

@app.route('/update_contact/<int:id>', methods=['GET', 'POST'])
@require_login
@require_verification
def update_contact(id):
    contact = Contact.query.filter_by(id=id).first()
    if request.method == 'GET':
        return render_template('update_contact.html', contact=contact)
    if request.method == 'POST':
        contactName = request.form['name']
        reciever = request.form['phone-number']
        contact.contactName = contactName
        contact.reciever = reciever
        db.session.commit()
        return redirect('/user/contacts')

@app.route('/user/settings')
@require_login
@require_verification
def user_settings():
    user = User.query.filter_by(id=session.get('user_id')).first()
    return render_template('user_settings.html', user=user)

@app.route('/users/change_credentials', methods=['GET', 'POST'])
@require_login
@require_verification
def change_credentials():
    if request.method == 'GET':
        user = User.query.filter_by(id=session.get('user_id')).first()
        return render_template('change_credentials.html', user=user)
    if request.method == 'POST':
        new_username = request.form['username']
        new_phone = request.form['phone-number']
        hasWhatsappRes = request.form.get('has-whatsapp')
        hasWhatsapp = False if hasWhatsappRes == None else True

        user = User.query.filter_by(id=session.get('user_id')).first()
        user.username = new_username
        user.phone = new_phone
        user.hasWhatsapp = hasWhatsapp

        db.session.commit()

        return redirect('/home')

# PAYMENT ROUTES

@app.route('/payment_form')
@require_login
@require_verification
def payment_form():
    return render_template('payment_form.html')

@app.route('/payment', methods=['POST'])
def payment():
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"},
        "redirect_urls": {
            "return_url": "http://localhost:3000/payment/execute",
            "cancel_url": "http://localhost:3000/"},
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": "testitem",
                    "sku": "12345",
                    "price": "10.00",
                    "currency": "USD",
                    "quantity": 1}]},
            "amount": {
                "total": "10.00",
                "currency": "USD"},
            "description": "This is the payment transaction description."}]})

    if payment.create():
        user = User.query.filter_by(id=session.get('user_id')).first()
        data = Payment(bill=10, status='created', plan='100 points', payer=user)
        db.session.add(data)
        db.session.commit()
        session['payment_id'] = data.id
    else:
        data = Payment(bill=10, status='failed', plan='100 points', payer=user)
        db.session.add(data)
        db.session.commit()
        return redirect(url_for('payment_error', error=payment.error))

    return jsonify({'paymentID' : payment.id})

@app.route('/execute', methods=['POST'])
def execute():
    success = False
    payment = paypalrestsdk.Payment.find(request.form['paymentID'])

    if payment.execute({'payer_id' : request.form['payerID']}):
        myPayment = Payment.query.filter_by(id=session.get('payment_id')).first()
        print('Success execute')
        succes = True
        user = User.query.filter_by(id=session.get('user_id')).first()
        user.points += 100
        myPayment.status = 'success'
        db.session.commit()
    else:
        myPayment = Payment.query.filter_by(id=session.get('payment_id')).first()
        myPayment.status = 'failed'
        db.session.commit()
        return redirect(url_for('payment_error', error=payment))
        print(payment.error)

    return jsonify({'success' : success})

@app.route('/payment/error/<error>')
def payment_error(error):
    return render_template('payment_error', error=error)

if __name__ == '__main__':
    app.run(debug=debug)