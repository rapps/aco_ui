import base64

import markupsafe
from flask import Flask, render_template, abort
from flask_paginate import get_page_args, Pagination
from flask_simplelogin import SimpleLogin
from lxml import etree, html

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
    data_page = OeazArticle.get_paginated(skip=offset, limit=per_page, query={"source": 1})
    pagination = Pagination(page=page, per_page=per_page, total=OeazArticle.count())
    return render_template('index.html', data_page=data_page, pagination=pagination)

@app.get('/detail/<article_id>')
def detail(article_id:int):
    article:OeazArticle = OeazArticle.get(id=int(article_id))
    if not article:
        abort(404)
    images = []
    toc = []
    try:
        s_issue:OeazStructuredIssue = OeazStructuredIssue(**[i for i in OeazStructuredIssue.get_dicts_by_query({"sort_nr": article.sort_nr})][0])

        #for p in s_issue.toc:
        articles = [OeazArticle(**a) for a in OeazArticle.get_dicts_by_query({"pubdate": article.pubdate, })]
        # _id = f"{s_issue.pubdate.strftime('%Y%m%d')}_{save_id_from_title(p.title)}"
        # _excl = True if not OeazArticle.get(_id) else False
        # _title = p.title[0:20]
        for a in articles:
            toc.append({"url": f"/detail/{a.id}", "title": a.title})
        images = [base64.b64encode(ACOFile.get_by_objid(i).source).decode() for i in article.images]

    except:
        s_issue = None # oeaz_online!

    article.html_raw = [markupsafe.Markup(etree.tounicode(a)) for a in html.fromstring(article.html_raw).xpath("//body/*")]
    return render_template('article_detail.html', article=article, toc=toc, images=images)

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)