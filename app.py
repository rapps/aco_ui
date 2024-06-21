import base64

import markupsafe
from flask import Flask, render_template, abort
from flask_paginate import get_page_args, Pagination
from flask_simplelogin import SimpleLogin
from lxml import etree

from helpers.save_article_id import save_id_from_title
from models.file import ACOFile
from models.oeaz_structured import OeazArticle, OeazStructuredIssue

app = Flask(__name__, template_folder='templates', static_folder="static")
app.config['SECRET_KEY'] = 'something-secret'
app.config['SIMPLELOGIN_USERNAME'] = 'apo'
app.config['SIMPLELOGIN_PASSWORD'] = 'pass123!'
SimpleLogin(app)

@app.get('/')
def index():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    data_page = OeazArticle.get_paginated(skip=offset, limit=per_page)
    pagination = Pagination(page=page, per_page=per_page, total=OeazArticle.count())
    data_page = [a for a in data_page]
    return render_template('index.html', data_page=data_page, pagination=pagination)

@app.get('/detail/<article_id>')
def detail(article_id:str):
    #'20120227_saalfelden_2012:_45._wissenschaftliche_fortbildungswoche_fr_apotheker:_stiefkinder_der_arzneimittelentwicklung' --> does not find url swallows ?
    article:OeazArticle = OeazArticle.get(id=article_id)
    if not article:
        abort(404)
    s_issue:OeazStructuredIssue = OeazStructuredIssue(**[i for i in OeazStructuredIssue.get_dicts_by_query({"sort_nr": article.sort_nr})][0])
    toc = []
    for p in s_issue.toc:
        _id = f"{s_issue.pubdate.strftime('%Y%m%d')}_{save_id_from_title(p.title)}"
        _excl = True if not OeazArticle.get(_id) else False
        _title = p.title[0:20]
        toc.append({"url": f"/detail/{_id}", "title": _title, "class": "excluded" if _excl else None })
    pdf_pages = range(article.start_page_nr, article.end_page_nr + 1)
    pdfs = [base64.b64encode(ACOFile.get(id=f"{s_issue.id}_p{i}").source).decode() for i in pdf_pages]
    article.html_raw = [markupsafe.Markup(etree.tounicode(a)) for a in etree.fromstring(article.html_raw).xpath("//body/*")]
    return render_template('article_detail.html', article=article, toc=toc, pdf=pdfs)

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)