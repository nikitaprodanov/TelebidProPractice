from flask import Flask
from flask import render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from newsapi import NewsApiClient
from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://ptlsiaoajcxazd:6e85719e1c803aa2f580a8d3ed88afbbc45217121b71b74e99dcadbbc1f2f374@ec2-18-211-48-247.compute-1.amazonaws.com:5432/d25jq3qesd358i'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.Text())
    title = db.Column(db.Text())
    description = db.Column(db.Text())
    url = db.Column(db.Text())
    urlToImage = db.Column(db.Text())
    publishedAt = db.Column(db.Text())

    def __init__(self, author, title, description, url, urlToImage, publishedAt):
        self.author = author
        self.title = title
        self.description = description
        self.url = url
        self.urlToImage = urlToImage
        self.publishedAt = publishedAt

@app.route('/')
def hello_world():
    return render_template('all_articles.html', articles=Article.query.limit(20).all())

@app.route('/secret')
def secret():
    newsapi = NewsApiClient(api_key='cd3fbef90e6f4d57b54f67a19851d1cd')

    sources = newsapi.get_sources()

    source = 127
    while source < len(sources['sources']):
        all_articles = newsapi.get_everything(sources=sources['sources'][source]['id'])
        for article in all_articles['articles']:
            author = article['author']
            title = article['title']
            description = article['description']
            url = article['url']
            urlToImage = article['urlToImage']
            publishedAt = article['publishedAt']

            data = Article(author=author, title=title, description=description, url=url, urlToImage=urlToImage, publishedAt=publishedAt)
            db.session.add(data)
            db.session.commit()
        
        source += 1
        print(str(source) + str(sources['sources'][source]['id']))
    

@app.route('/searched', methods=['POST'])
def searched():
    if request.method == 'POST':
        fromDate = str(request.form['from'])
        toDate = str(request.form['to'])

        articles = Article.query.filter(Article.publishedAt.between(fromDate, toDate)).order_by(Article.publishedAt.desc()).all()

        return render_template('searched_articles.html', articles=articles, fromDate=fromDate, toDate=toDate)

if __name__ == "__main__":
	app.run(debug=True)