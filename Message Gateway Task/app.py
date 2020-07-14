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

class Distributor(db.Model):
    __tablename__ = "distributors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text())
    cost = db.Column(db.Float())

    def __init__(self, name, cost):
        self.name = name
        self.cost = cost

class Plan(db.Model):
    __tablename__ = "plans"
    id = db.Column(db.Integer, primary_key=True)
    points = db.Column(db.Integer())
    cost = db.Column(db.Float())
    name = db.Column(db.Text())

    def __init__(self, points, cost, name):
        self.points = points
        self.cost = cost
        self.name = name
        

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

            msg = Message('Confirmation Email', sender='nikitaprodanov20@gmail.com', recipients=[email])
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

        msg = Message('Confirmation Email', sender='nikitaprodanov20@gmail.com', recipients=[email])
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
        distributor = Distributor.query.filter_by(name='SMS').first()

        user = User.query.filter_by(id=session.get('user_id')).first()
        if user.points < distributor.cost:
            plans = Plan.query.all()
            return redirect(url_for('payment_form', plans=plans))

        account_sid = app.config['SMS_SID']
        auth_token = app.config['SMS_TOKEN']
        client = Client(account_sid, auth_token)

        reciever = request.form['phone-number']
        msg = "This is automated sms from {}: {}".format(request.form['from'], request.form['message'])
        tax = distributor.cost
        sender = User.query.filter_by(id=session.get('user_id')).first()

        contact = Contact.query.filter_by(owner=sender, reciever=reciever, method='sms').first()

        if contact:
            reciever = contact.contactName
        
        data = SMS(reciever=reciever, message=msg, tax=tax, status='queued', sender=sender)
        db.session.add(data)
        db.session.commit()
        session['message_id'] = data.id

        try:
            sms = client.messages.create(
                from_="+12018317102",
                body=msg,
                to=request.form['phone-number']
            )

            sender.points -= tax
            data.status = 'delivered'
            db.session.commit()

            return redirect(url_for('success_sms'))
        except:
            message = SMS.query.filter_by(id=session.get('message_id')).first()
            message.status = 'failed'
            db.session.commit()
            return redirect(url_for('sms_error'))

@app.route('/send_whatsapp', methods=['GET', 'POST'])
@require_login
@require_verification
def send_whatsapp():
    if request.method == 'GET':
        return render_template('send_whatsapp.html')
    if request.method == 'POST':
        distributor = Distributor.query.filter_by(name="whatsapp").first()

        user = User.query.filter_by(id=session.get('user_id')).first()
        if user.points < distributor.cost:
            plans = Plan.query.all()
            return redirect(url_for('payment_form', plans=plans))

        account_sid = app.config['WHATSAPP_SID']
        auth_token = app.config['WHATSAPP_TOKEN']

        client = Client(account_sid, auth_token)

        from_whatsapp_number = 'whatsapp:+14155238886'
        to_whatsapp_number = 'whatsapp:{}'.format(request.form['phone-number'])
        if to_whatsapp_number != 'whatsapp:+359893294474':
            return redirect(url_for('whatsapp_error'))

        reciever = to_whatsapp_number
        msg = "This is automated message from {}: {}".format(request.form['from'], request.form['message'])
        tax = distributor.cost
        sender = User.query.filter_by(id=session.get('user_id')).first()

        contact = Contact.query.filter_by(owner=sender, reciever=to_whatsapp_number, method='whatsapp').first()

        if contact:
            reciever = contact.contactName
        
        data = SMS(reciever=reciever, message=msg, tax=tax, status='delivered', sender=sender)
        db.session.add(data)
        db.session.commit()
        session['message_id'] = data.id

        try:
            client.messages.create(body=msg,
                        from_=from_whatsapp_number,
                        to=to_whatsapp_number)

            sender.points -= tax
            db.session.commit()
            
            return redirect(url_for('success_whatsapp'))
        except:
            message = SMS.query.filter_by(id=session.get('message_id')).first()
            message.status = 'failed'
            return redirect(url_for('whatsapp_error'))

@app.route('/send_sms/error')
@require_login
@require_verification
def sms_error():
    return render_template('sms_error.html')

@app.route('/send_whatsapp/error')
@require_login
@require_verification
def whatsapp_error():
    return render_template('whatsapp_error.html')

@app.route('/send_sms/sucsess')
@require_login
@require_verification
def success_sms():
    return render_template('success_sms.html')

@app.route('/send_whatsapp/sucsess')
@require_login
@require_verification
def success_whatsapp():
    return render_template('success_whatsapp.html')
    
@app.route('/user/sent_sms', methods=['GET', 'POST'])
@require_login
@require_verification
def sent_sms():
    if request.method == 'GET':
        user = User.query.filter_by(id=session.get('user_id')).first()
        messages = SMS.query.filter_by(senderId=user.id).order_by(SMS.sendDate.desc()).limit(10).all()
        return render_template('sent_sms_list.html', messages=messages, user=user)
    if request.method == 'POST':
        fromDate = str(request.form['from'])
        toDate = str(str(request.form['to']) + " 23:59:59")
        user = User.query.filter_by(id=session.get('user_id')).first()
        messages = SMS.query.filter(SMS.sendDate >= fromDate, SMS.sendDate <= toDate, SMS.senderId==user.id).order_by(SMS.sendDate.desc()).all()
        return render_template('sent_sms_list.html', messages=messages, user=user)

@app.route('/user/contacts')
@require_login
@require_verification
def user_contacts():
    user = User.query.filter_by(id=session.get('user_id')).first()
    contacts = user.contacts
    return render_template('user_contacts.html', contacts=contacts)

@app.route('/user/payments', methods=['GET', 'POST'])
@require_login
@require_verification
def user_payments():
    if request.method == 'GET':
        user = User.query.filter_by(id=session.get('user_id')).first()
        payments = Payment.query.filter_by(payerId=user.id).order_by(Payment.payDate.desc()).limit(10).all()
        return render_template('user_payments.html', payments=payments)
    if request.method == 'POST':
        fromDate = str(request.form['from'])
        toDate = str(str(request.form['to']) + " 23:59:59")
        user = User.query.filter_by(id=session.get('user_id')).first()
        payments = Payment.query.filter(Payment.payDate >= fromDate, Payment.payDate <= toDate, Payment.payerId==user.id).order_by(Payment.payDate.desc()).all()
        return render_template('user_payments.html', payments=payments)

@app.route('/send_sms_from_contacts/<reciever>/<method>')
@require_login
@require_verification
def send_message_from_contacts(reciever, method):
    if method == 'whatsapp':
        return render_template('send_from_contact_whatsapp.html', reciever=reciever)
    if method == 'sms':
        return render_template('send_from_contact_sms.html', reciever=reciever)

@app.route('/new_contact', methods=['GET', 'POST'])
@require_login
@require_verification
def new_contact():
    if request.method == 'GET':
        return render_template('new_contact.html')
    if request.method == 'POST':
        reciever = request.form['phone-number']
        contactName = request.form['name']
        method = request.form['options']
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
        method = request.form['options']
        contact.contactName = contactName
        contact.reciever = reciever
        contact.method = method
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
    plans = Plan.query.all()
    return render_template('payment_form.html', plans=plans)

@app.route('/plan_checkout/<id>')
@require_login
@require_verification
def plan_checkout(id):
    plan = Plan.query.filter_by(id=id).first()
    return render_template('plan_checkout.html', plan=plan)

@app.route('/payment/<id>', methods=['POST'])
def payment(id):
    plan = Plan.query.filter_by(id=id).first()
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
                    "name": str(plan.name),
                    "sku": "12345",
                    "price": str(plan.cost),
                    "currency": "USD",
                    "quantity": 1}]},
            "amount": {
                "total": str(plan.cost),
                "currency": "USD"},
            "description": "This is the payment transaction description."}]})

    if payment.create():
        user = User.query.filter_by(id=session.get('user_id')).first()
        data = Payment(bill=plan.cost, status='cancelled', plan=plan.name, payer=user)
        db.session.add(data)
        db.session.commit()
        session['payment_id'] = data.id
    else:
        data = Payment(bill=10, status='failed', plan=plan.name, payer=user)
        db.session.add(data)
        db.session.commit()
        print(payment.error)
        return redirect(url_for('payment_error', error=payment.error))

    return jsonify({'paymentID' : payment.id})

@app.route('/execute', methods=['POST'])
def execute():
    success = False
    payment = paypalrestsdk.Payment.find(request.form['paymentID'])
    myPayment = Payment.query.filter_by(id=session.get('payment_id')).first()
    myPayment.status = 'failed'
    db.session.commit()

    if payment.execute({'payer_id' : request.form['payerID']}):
        print('Success execute')
        succes = True
        user = User.query.filter_by(id=session.get('user_id')).first()
        plan = Plan.query.filter_by(name=myPayment.plan).first()
        user.points += plan.points
        myPayment.status = 'success'
        db.session.commit()
    else:
        myPayment.status = 'failed'
        db.session.commit()
        print(payment.error)
        return redirect(url_for('payment_error', error=payment))

    return jsonify({'success' : success})

@app.route('/payment/error/<error>')
def payment_error(error):
    return render_template('payment_error', error=error)

# BACK OFFICE

def require_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for(admin_authenticate))
        return func(*args, **kwargs)
    return wrapper

@app.route('/backoffice')
def backoffice():
    if session.get('admin'):
        return redirect(url_for('admin_home'))
    return redirect(url_for('admin_authenticate'))

@app.route('/backoffice/authenticate', methods=['GET', 'POST'])
def admin_authenticate():
    if request.method == 'GET':
        return render_template('backoffice_authenticate.html')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username != app.config['ADMINS_USERNAME'] or password != app.config['ADMIN_PASSWORD']:
            return redirect(url_for('admin_authenticate'))
        
        session['admin']=True
        return redirect(url_for('admin_home'))

@app.route('/backoffice/home')
@require_admin
def admin_home():
    today = str(str(datetime.utcnow().date()) + " 00:00:00")
    messages = SMS.query.filter(SMS.sendDate >= today).count()
    payments = Payment.query.filter(Payment.payDate >= today).count()
    return render_template('admin_home.html', payments=payments, messages=messages)

@app.route('/backoffice/messages', methods=['GET', 'POST'])
@require_admin
def admin_messages():
    if request.method == 'GET':
        today = str(str(datetime.utcnow().date()) + " 00:00:00")
        messages = SMS.query.filter(SMS.sendDate >= today).all()
        return render_template('admin_messages.html', messages=messages)
    if request.method == 'POST':
        fromDate = str(request.form['from'])
        toDate = str(str(request.form['to']) + " 23:59:59")
        messages = SMS.query.filter(SMS.sendDate >= fromDate, SMS.sendDate <= toDate).order_by(SMS.sendDate.desc()).all()
        return render_template('admin_messages.html', messages=messages)

@app.route('/backoffice/payments', methods=['GET', 'POST'])
@require_admin
def admin_payments():
    if request.method == 'GET':
        today = str(str(datetime.utcnow().date()) + " 00:00:00")
        payments = Payment.query.filter(Payment.payDate >= today).all()
        return render_template('admin_payments.html', payments=payments)
    if request.method == 'POST':
        fromDate = str(request.form['from'])
        toDate = str(str(request.form['to']) + " 23:59:59")
        payments = Payment.query.filter(Payment.payDate >= fromDate, Payment.payDate <= toDate).order_by(Payment.payDate.desc()).all()
        return render_template('admin_payments.html', payments=payments)

@app.route('/backoffice/user_activity', methods=['GET', 'POST'])
@require_admin
def user_activity():
    if request.method == 'GET':
        return render_template('find_user.html')
    if request.method == 'POST':
        id = int(request.form['id'])
        if id <= 0:
            return redirect(url_for('searched_user_error'))
        user = User.query.filter_by(id=id).first()
        if not user:
            return redirect(url_for('searched_user_error'))
        messages = user.messages
        payments = user.payments
        return render_template('user_activity.html', user=user, messages=messages, payments=payments)

@app.route('/backoffice/user_activity/error')
def searched_user_error():
    return render_template('searched_user_error.html')

@app.route('/backoffice/plans_catalogue')
@require_admin
def plans_catalogue():
    plans = Plan.query.all()
    return render_template('plans_catalogue.html', plans=plans)

@app.route('/backoffice/plan_edit/<int:id>', methods=['GET', 'POST'])
@require_admin
def edit_plan(id):
    if request.method == 'GET':
        plan = Plan.query.filter_by(id=id).first()
        return render_template('edit_plan.html', plan=plan)
    if request.method == 'POST':
        plan = Plan.query.filter_by(id=id).first()
        points = int(request.form['points'])
        cost = float(request.form['cost'])
        name = request.form['name']
        if cost <= 0 or points <= 0:
            return redirect(url_for('edit_plan_error', id=id))
        plan.points = points
        plan.cost = cost
        plan.name = name
        db.session.commit()
        return redirect(url_for('plans_catalogue'))

@app.route('/backoffice/plan_edit/error/<int:id>')
def edit_plan_error(id):
    return render_template('edit_plan_error.html', id=id)

@app.route('/backoffice/new_plan', methods=['GET', 'POST'])
@require_admin
def new_plan():
    if request.method == 'GET':
        return render_template('new_plan.html')
    if request.method == 'POST':
        points = int(request.form['points'])
        cost = float(request.form['cost'])
        name = request.form['name']
        if cost <= 0 or points <= 0:
            return redirect(url_for('new_plan_error'))
        data = Plan(points=points, cost=cost, name=name)
        db.session.add(data)
        db.session.commit()
        return redirect(url_for('plans_catalogue'))

@app.route('/backoffice/new_plan/error')
def new_plan_error():
    return render_template('new_plan_error.html')

@app.route('/backoffice/message_taxes')
@require_admin
def message_taxes():
    distributors = Distributor.query.all()
    return render_template('message_taxes.html', distributors=distributors)

@app.route('/backoffice/edit_tax/<int:id>', methods=['GET', 'POST'])
@require_admin
def edit_tax(id):
    if request.method == 'GET':
        distributor = Distributor.query.filter_by(id=id).first()
        return render_template('edit_tax.html', distributor=distributor)
    if request.method == 'POST':
        distributor = Distributor.query.filter_by(id=id).first()
        cost = float(request.form['cost'])
        if cost <= 0:
            return redirect(url_for('edit_tax_error', id=id))
        distributor.cost = cost
        db.session.commit()
        return redirect(url_for('message_taxes'))
        
@app.route('/backoffice/edit_tax/error/<int:id>')
def edit_tax_error(id):
    return render_template('edit_tax_error.html', id=id)


if __name__ == '__main__':
    app.run(debug=debug)