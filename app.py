import base64
import json

import markupsafe
from flask import Flask, render_template, abort
from flask_paginate import get_page_args, Pagination
from flask_simplelogin import SimpleLogin
from lxml import etree, html

from helpers.save_article_id import save_id_from_title
from models.aco import ACOMeta
from models.file import ACOFile
from models.oeaz_structured import OeazArticle, OeazStructuredIssue

app = Flask(__name__, template_folder='templates', static_folder="static")
app.config['SECRET_KEY'] = 'something-secret'
app.config['SIMPLELOGIN_USERNAME'] = 'apo'
app.config['SIMPLELOGIN_PASSWORD'] = 'pass123!'
SimpleLogin(app)

@app.get('/oeaz', defaults={'year': None, 'month': None})
@app.get('/oeaz/<int:year>/<int:month>/')
def index_oeaz(year=None, month=None):
    # page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    # pagination = Pagination(page=page, per_page=per_page, total=OeazArticle.count())
    treelist = OeazArticle.get_pubyear_tree()
    tree_str = json.dumps(treelist)
    if not month:
        year = treelist[-1]["text"]
        month = treelist[-1]["nodes"][-1]["text"]
    data_page = OeazArticle.get_by_month_and_year_sorted(month=month, year=year, sort=1)
    return render_template('index_oeaz.html', data_page=data_page, tree=tree_str)

@app.get('/') #aco aco/
@app.get('/aco/<bez_start>/')
def index_aco(bez_start=None):
    treelist = ACOMeta.get_by_name_groups()
    tree_str = json.dumps(treelist)
    if bez_start is None:
        bez_start = treelist[0]["nodes"][0]["text"]
    data_page = ACOMeta.get_by_bez_start(bez_start)
    return render_template('index_aco.html', data_page=data_page, tree=tree_str)


@app.get('/oeaz/detail/<article_id>/')
def detail_article(article_id:int):
    article:OeazArticle = OeazArticle.get(id=int(article_id))
    if not article:
        abort(404)
    treelist = OeazArticle.get_pubmonth_tree(year=article.pubdate.year, month=article.pubdate.month)
    tree_str = json.dumps(treelist)

    images = [base64.b64encode(ACOFile.get_by_objid(i).source).decode() for i in article.images]

    article.html_raw = [markupsafe.Markup(etree.tounicode(a)) for a in html.fromstring(article.html_raw).xpath("//body/*")]
    return render_template('detail_oeaz.html', article=article, tree=tree_str, images=images)

@app.get('/aco/detail/<aco_id>/')
def detail_aco(aco_id:int):
    #todo: ACOMeta id needs int id
    aco:ACOMeta = ACOMeta.get(id=aco_id)
    if not aco:
        abort(404)
    treelist = ACOMeta.get_by_name_groups()
    tree_str = json.dumps(treelist)

    #article.html_raw = [markupsafe.Markup(etree.tounicode(a)) for a in html.fromstring(article.html_raw).xpath("//body/*")]
    return render_template('detail_aco.html', aco=aco, tree=tree_str)



@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)