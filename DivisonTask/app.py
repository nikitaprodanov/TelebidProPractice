from flask import Flask
from flask import render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://fnbtilcgbstqur:6e3df13b9be3088de48b1421456f4d76900d076f286b926ed1f6202626f6059d@ec2-50-19-26-235.compute-1.amazonaws.com:5432/dfvc95cghcgv7v'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text(), nullable=False)
    dividend = db.Column(db.Integer, nullable=False)
    divisor = db.Column(db.Integer, nullable=False)

    def __init__(self, username, dividend, divisor):
        self.username = username
        self.dividend = dividend
        self.divisor = divisor

@app.route('/')
def hello_world():
    return redirect('divide_form')

@app.route('/divide_form', methods=['GET', 'POST'])
def dividng():
    if request.method == 'GET':
        return render_template('divide.html')
    elif request.method == 'POST': 
        username = request.form['username']
        dividend = request.form['dividend']
        divisor = request.form['divisor']

        if int(divisor) == 0:
            return redirect(url_for('zero_division'))
        else:
            data = User(username, dividend, divisor)
            db.session.add(data)
            db.session.commit()

            users = User.query.filter_by(username=username, dividend=dividend, divisor=divisor).all()

            return render_template('result.html', user=users[-1])

@app.route('/zero_division', methods=['GET'])
def zero_division():
    return render_template('zero.html')

if __name__ == "__main__":
	app.run(debug=True)