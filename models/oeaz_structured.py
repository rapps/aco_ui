import collections
import datetime
import json
from pathlib import Path
from typing import List, Union, Generator, Dict, Literal, Optional

from pydantic import BaseModel
from pydantic_mongo import PydanticObjectId
from pymongo.errors import DuplicateKeyError

import settings
from db.mongo import oeaz_structured, LongSessionCursor, oeaz_article

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


class OeazArticle(BaseModel):
    id: str
    nummer: int
    sort_nr: int
    jahrgang: int
    start_page_nr: int
    end_page_nr: int
    rubrik: str
    title: str
    html_raw: str = ""
    created: datetime.datetime = datetime.datetime.now()
    pubdate: Union[datetime.datetime, None] = None
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
    def get(id: str) -> Union['OeazArticle', None]:
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
    def delete(id: str) -> None:
        oeaz_article.delete_one({"id": id})

    @staticmethod
    def count():
        return oeaz_article.count_documents({})