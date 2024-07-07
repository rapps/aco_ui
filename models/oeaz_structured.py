import collections
import datetime
import json
import re
from pathlib import Path
from string import Template
from typing import List, Union, Generator, Dict, Literal, Optional, Any

from lxml import etree, html
import html as html_
from pydantic import BaseModel
from pydantic_mongo import PydanticObjectId
from pymongo.errors import DuplicateKeyError

import settings
from db.mongo import oeaz_structured, LongSessionCursor, oeaz_article
from helpers.ws import replaceWS
from models.file import ACOFile

logger = settings.logger

# RUBRIKEN = {
#     0: "Keine",
#     1: "Pharmazie Tara Medizin",
#     2: "Politik Recht Wirtschaft",
#     3: "Krankenhaus Pharmazie",
#     4: "Chronik & Historie",
#     5: "Mitteilungen & Termine",
# }


class OeazStructuredPage(BaseModel):
    id: str
    nummer: int
    sort_nr: int
    jahrgang: int
    page_nr: int
    md_raw: str
    md: str
    meta: str
    type:Literal["Ignore","Title", "TOC", "Promo", "Editorial"] = 'Editorial'
    created: datetime.datetime = datetime.datetime.now()
    processed: int = 0

class OeazTocEntry(BaseModel):
    page_nr: int
    title: str
    section: Optional[str]=None

    @staticmethod
    def get_from_file(filepath:Path) -> List['OeazTocEntry']:
        with open(filepath) as f:
            raw_toc = json.loads(f.read())
        toc = sorted(raw_toc, key=lambda x: x["page_nr"])
        #try reducing doubles by dict (assume last/all) are ok)
        toc_dict = { entry["page_nr"]: OeazTocEntry(**entry) for entry in toc}
        result:List['OeazTocEntry'] = list(toc_dict.values())
        return result

class OeazStructuredIssue(BaseModel):
    id: int
    nummer: int
    sort_nr: int
    jahrgang: int
    pages: List[OeazStructuredPage]
    created: datetime.datetime = datetime.datetime.now()
    pubdate: datetime.datetime
    toc: List[OeazTocEntry] = []
    processed: int = 0

    def get_toc(self) -> Union[Dict, None]:
        try:
            toc = json.loads([page for page in self.pages if page.is_toc][0].json)
        except:
            logger.warning(f"no toc present for {self.id}")
            return None
        return toc

    # def get_editorial_toc_entries(self) -> Dict[int, str]:
    #     start_pages = {}
    #     for r in self.get_toc():
    #         for k, v in r.items():
    #             for entry in v:
    #                 start_pages.update(entry)
    #     return collections.OrderedDict(sorted(start_pages.items(), key=lambda kv: kv[1]))

    def save(self) -> 'OeazStructuredIssue':
        try:
            oeaz_structured.insert_one(self.dict())
        except DuplicateKeyError as e:
            query = {"id": self.id}
            newvalues = {"$set": self.dict()}
            oeaz_structured.update_one(query, newvalues)
        except Exception as eg:
            logger.exception("Something wrong with the save")
        return self

    @staticmethod
    def get_objid(id: int) -> Union[PydanticObjectId, None]:
        issue = oeaz_structured.find_one({"id": id})
        if issue is None: return None
        return PydanticObjectId(issue["_id"])

    @staticmethod
    def get(id: int) -> Union['OeazPdfIssue', None]:
        issue = oeaz_structured.find_one({"id": id})
        if issue is None: return None
        return OeazStructuredIssue(**issue)

    @staticmethod
    def get_dicts_by_query(query: Dict) -> Generator:
        lsc = LongSessionCursor(oeaz_structured, query)
        return lsc.iter()



class OeazAuthor(BaseModel):
    title_pre:Union[str,None]=None
    title_post:Union[str,None]=None
    first_name:str
    last_name:str
    url:Union[str,None]=None

    @staticmethod
    def from_dict(indict:Dict[str,str]) ->Union['OeazAuthor', None]:
        try:
            author = OeazAuthor(
                title_pre=replaceWS(indict["titlepre"]) if "titlepre" in indict else None,
                title_post = replaceWS(indict["titlepost"]) if "titlepost" in indict else None,
                first_name = replaceWS(indict["firstname"]).strip(),
                last_name = replaceWS(indict["lastname"]).strip(),
                path = indict["path"].strip()
            )
            return author
        except:
            logger.warning(f"could not parse author: {indict}")
            return None

    def to_link(self) -> str:
        return  f"<a href='{self.path}'>{self.title_pre + ' ' if self.title_pre else ''}{self.first_name} {self.last_name}{' ' +self.title_post if self.title_post else ''}</a>"


class OeazKeyword(BaseModel):
    name: str
    type: Literal["trade_name", "substance", "disease"]

    def __str__(self):
        return self.name

    def __hash__(self):
        print(hash(str(self)))
        return hash(str(self))

    def __eq__(self,other):
        return self.name == other.name


class OeazMeta(BaseModel):
    summary: str
    keywords: List[OeazKeyword] = []


class OeazArticle(BaseModel):
    id: int
    nummer: int
    sort_nr: int
    jahrgang: int
    start_page_nr: int
    end_page_nr: int
    rubrik: str
    title: str
    html_raw: str = ""
    created: datetime.datetime = datetime.datetime.now()
    pubdate: datetime.datetime
    url:Union[str, None] = None
    author:List[OeazAuthor]=[]
    images: List[PydanticObjectId] = []
    teaser: Union[str, None] = None
    source: int=0 # 0 = oeaz_oline, 1 = archive
    meta: Union[OeazMeta, None] = None
    processed: int = 0

    def save(self) -> 'OeazArticle':
        try:
            oeaz_article.insert_one(self.dict())
        except DuplicateKeyError as e:
            query = {"id": self.id}
            newvalues = {"$set": self.dict()}
            oeaz_article.update_one(query, newvalues)
        except Exception as eg:
            logger.exception("Something wrong with the save")
        return self

    @staticmethod
    def get(id: int) -> Union['OeazArticle', None]:
        art = oeaz_article.find_one({"id": id})
        if art is None: return None
        return OeazArticle(**art)

    @staticmethod
    def get_dicts_by_query(query: Dict) -> Generator:
        lsc = LongSessionCursor(oeaz_article, query)
        return lsc.iter()

    @staticmethod
    def get_paginated(skip:int, limit:int):
        return [OeazArticle(**item) for item in oeaz_article.find().sort("pubdate", 1).skip(skip).limit(limit)]

    @staticmethod
    def delete(id: int) -> None:
        oeaz_article.delete_one({"id": id})

    @staticmethod
    def count():
        return oeaz_article.count_documents({})


    @staticmethod
    def from_rest_dict(in_dict) -> 'OeazArticle':
        #content
        templatepath = settings.BASEPATH.joinpath("assets", "templates", "article_template.html")
        with open(templatepath, "r") as f:
            template = Template(f.read())
        try:
            title = " ".join([i if isinstance(i, str) else etree.tounicode(i) for i in in_dict["title"]])
            subtitle =" ".join([i if isinstance(i, str) else etree.tounicode(i) for i in in_dict["subtitle"]])
            teasertext = "".join([i if isinstance(i, str) else etree.tounicode(i) for i in in_dict["teasertext"]])
            content = "\n".join([f"<p>{html_.escape(i)}</p>" if isinstance(i, str) else etree.tounicode(i) for i in in_dict["pagecontent"]])

        except Exception as e:
            logger.warning("Content serialization failed - ignoring article...")
            return

        html_raw = template.substitute(
            id=in_dict["cms_id"],
            rubrik=in_dict["channelnameraw"],
            title=title,
            subtitle = subtitle,
            teasertext = teasertext,
            content = content,
            tags = ",".join(f"<span class='tag'>{tag}</span>" for tag in in_dict["tags"])
        )
        # remove styles & images (will blow up GPT cost)
        doc = html.fromstring(html_raw)
        for n in doc.xpath("//*"):
            if "style" in n.attrib:
                del n.attrib["style"]
            if n.tag == "img":
                n.getparent().replace(n, html.fragment_fromstring("<span class='removed_image' />"))
        teaser = re.sub(r"\s+", " ", " ".join([i if isinstance(i, str) else ' '.join(i.itertext()) for i in in_dict["teasertext"]]))
        title = " ".join([i if isinstance(i, str) else ' '.join(i.itertext()) for i in in_dict["title"]])
        title += " "
        title += " ".join([i if isinstance(i, str) else ' '.join(i.itertext()) for i in in_dict["subtitle"]])
        title = re.sub(r"\s+", " ", title).strip()

        author = []
        if "authorjson" in in_dict:
            if isinstance(in_dict["authorjson"], list):
                for d in in_dict["authorjson"]:
                    a = OeazAuthor.from_dict(d)
                    if a: author.append(a)
            else:
                a = OeazAuthor.from_dict(in_dict["authorjson"])
                if a: author.append(a)
        else: author = []

        jahrgang = in_dict["publishtimestamp"].year
        nummer = int(f'{in_dict["publishtimestamp"].month:02}{in_dict["publishtimestamp"].day:02}') # unknown!
        art_idx = int(f'{jahrgang}{in_dict["cms_id"]:05}') #dms id!
        start_page_nr=0 #unknown!
        end_page_nr=0 #unknown!

        return OeazArticle(
            id=art_idx,
            nummer=nummer,
            sort_nr=int(f"{jahrgang}{nummer}"),
            jahrgang=jahrgang,
            start_page_nr= start_page_nr,
            end_page_nr= end_page_nr,
            rubrik = in_dict["channelnameraw"],
            title = title,
            html_raw=html_raw,
            created=in_dict["createdate"],
            pubdate=in_dict["publishtimestamp"],
            url=in_dict["url"],
            author=author,
            teaser = teaser,
        )

    @staticmethod
    def get_month_and_year_dict() -> list[Any]:
        return  list(oeaz_article.aggregate([
                {"$sort": {"id": 1}},
                {"$group":
                    {"_id": {
                        "year": {"$year": "$pubdate"},
                        "month": {"$month": "$pubdate"}
                        },
                    },
                },
                {"$sort": {"_id": -1}},
        ]))
    @staticmethod
    def get_pubyear_tree() -> List:
        test = OeazArticle.get_month_and_year_dict()
        tree = {}
        tree_list = []
        for i in test:
            year = i["_id"]['year']
            month = i["_id"]['month']
            if year in tree:
                tree[year][month] = {}
            else:
                tree[year] = {month: {}}
        for year, months in tree.items():
            y_node = {
                "text": year,
                "icon": "fa fa-inbox fa-fw",
                "nodes": []
            }
            tree_list.append(y_node)
            for month, articles in months.items():
                m_node = {
                    "text": month,
                    "icon": "fa fa-inbox fa-fw",
                    "class": "text-info",
                    "href": f"/oeaz/{year}/{month}/"
                }
                y_node["nodes"].append(m_node)
                # for article in articles:
                #     a_node = {
                #         "text": article["title"],
                #         "icon": "fa fa-inbox fa-fw",
                #         "class": "text-info",
                #         "href": f"/detail/{article['id']}/"
                #     }
                #     m_node["nodes"].append(a_node)
        return tree_list

    @staticmethod
    def get_pubmonth_tree(year:int, month:int) -> List:
        tree_list = []
        articles = OeazArticle.get_by_month_and_year_sorted(year=year, month=month, sort=1)
        for article in articles:
            a_node = {
                "text": article.title,
                "icon": "fa fa-inbox fa-fw",
                "class": "text-info",
                "href": f"/oeaz/detail/{article.id}/"
            }
            tree_list.append(a_node)

        return tree_list

    @staticmethod
    def get_by_month_and_year_sorted(month:int, year:int, sort:int):
        query = {
            "$expr": {
                "$and": [{"$eq": [{"$month": "$pubdate"}, month]},
                         {"$eq": [{"$year": "$pubdate"}, year]}]
            }
        }
        return [OeazArticle(**item) for item in oeaz_article.find(query).sort("id", sort)]

    def add_gpt_meta(self, gpt_meta:Dict):
        meta = OeazMeta(**{
            "summary": gpt_meta["summary_article"],
            "keywords": []
        })

        for kw in gpt_meta["trade_names"]:
            meta.keywords.append(
                OeazKeyword(
                    name=kw["name"],
                    type="trade_name"
                ))
            if 'synonym' in kw:
                for s in kw["synonym"]:
                    meta.keywords.append(OeazKeyword(
                        name=s,
                        type="trade_name"
                    ))

        for kw in gpt_meta["substances"]:
            meta.keywords.append(
                OeazKeyword(
                    name=kw["name"],
                    type="substance"
                ))
            if 'synonym' in kw:
                for s in kw["synonym"]:
                    meta.keywords.append(OeazKeyword(
                        name=s,
                        type="substance"
                    ))

        for kw in gpt_meta["diseases"]:
            meta.keywords.append(
                OeazKeyword(
                    name=kw["name"],
                    type="disease"
                ))
            if 'synonym' in kw:
                for s in kw["synonym"]:
                    meta.keywords.append(
                        OeazKeyword(
                            name=s,
                            type="disease"
                        ))
        self.meta = meta
        self.processed = 2
        self.save()
        logger.info(f"--> {[k for k in self.meta.keywords]}")