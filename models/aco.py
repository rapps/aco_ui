from typing import Union, Any, Dict, List, Tuple, Generator

from pydantic import BaseModel
from pymongo import UpdateOne
from pymongo.errors import DuplicateKeyError

import settings
from db.mongo import sis, LongSessionCursor, aco
from models.sis import SISMeta

logger = settings.logger

class ACOActive(BaseModel):
    bezeichnung:str

class ACOKurztext(BaseModel):
    bezeichnung:str # probably enum
    text: Union[str, None]

class ACOPackage(BaseModel):
    pzn:int
    bezeichnung:str

class ACOGPTMeta(BaseModel):
    product_name: str
    dosage: Union[str, None] = None
    dosage_form: Union[str, None] = None

class ACOMeta(SISMeta):
    wirkstoffe: List[ACOActive]
    kurztexte: List[ACOKurztext]
    packungen:List[ACOPackage]
    meta:Union[ACOGPTMeta, None] = None
    processed:int=0

    @staticmethod
    def from_sismeta_and_aco_entries(sis_meta:SISMeta, aco_entry:Dict):
        packages = []
        actives = []
        kurztexte = []
        if len(aco_entry["errors"]):
            raise("; ".join(e for e in aco_entry["errors"]))
        for idx, entry in enumerate(aco_entry["masterdatarecords"]):
            packages.append(ACOPackage(**{
                "pzn": entry["medicine"]["pzn"],
                "bezeichnung": entry["medicine"]["packagename"]
            }))
            for a in entry["actives"]:
                aa = ACOActive(**{
                    "bezeichnung": a
                })
                if idx > 0:
                    try:
                        assert(aa in actives) # make sure there are no differing kt and actives
                    except:
                        logger.exception("differing actives when diff packs")
                else:
                    actives.append(aa)
            for a in entry["shorttexts"]:
                aa = ACOKurztext(**{
                    "bezeichnung": a["chapter"],
                    "text": a["content"]
                })
                if idx > 0:
                    try:
                        assert(aa in kurztexte) # make sure there are no differing kt and actives
                    except:
                        logger.exception("differing kt when diff packs")
                else:
                    kurztexte.append(aa)
        aco_dict = sis_meta.dict()
        aco_dict["wirkstoffe"] = actives
        aco_dict["packungen"] = packages
        aco_dict["kurztexte"] = kurztexte
        return ACOMeta(**aco_dict)

    @staticmethod
    def get(id: int) -> Union['OeazPdfIssue', None]:
        entry = aco.find_one({"id": id})
        if entry is None: return None
        return ACOMeta(**entry)

    @staticmethod
    def get_dicts_by_query(query: Dict) -> Generator:
        lsc = LongSessionCursor(aco, query)
        return lsc.iter()

    def save(self) -> 'ACOMeta':
        try:
             aco.insert_one(self.dict())
        except DuplicateKeyError as e:
             query = {"id": self.id}
             newvalues = {"$set": self.dict()}
             aco.update_one(query, newvalues)
        except Exception as eg:
             logger.exception("Something wrong with the save")
        return self

    @staticmethod
    def get_by_bez_start(bez_start: str):
        return [ACOMeta(**item) for item in
                ACOMeta.get_dicts_by_query({"bezeichnung": {'$regex': f'^{bez_start}.*', '$options': 'i'}})]

    @staticmethod
    def get_name_groups(substring_len: int) -> list[Any]:
        return list(aco.aggregate([
            {"$sort": {"bezeichnung": 1}},
            {"$group":
                {
                    "_id": {"$substrCP": ['$bezeichnung', 0, 3], },
                }
            },
            {"$sort": {"_id": 1}},
        ]))

    @staticmethod
    def get_by_name_groups():
        test = ACOMeta.get_name_groups(2)
        tree_list = []

        from collections import defaultdict

        groups = defaultdict(list)
        for entry in test:
            groups[entry["_id"][:1]].append(entry)
        for k, v in groups.items():
            abc_node = {
                "text": k,
                "icon": "fa fa-inbox fa-fw",
                "nodes": []
            }
            tree_list.append(abc_node)
            for entry in v:
                p_node = {
                    "text": entry["_id"],
                    "icon": "fa fa-inbox fa-fw",
                    "class": "text-info",
                    "href": f"/aco/{entry['_id']}/"
                }
                abc_node["nodes"].append(p_node)

        return tree_list

    @staticmethod
    def set_all_atrade():
        operations = []
        for a in ACOMeta.get_dicts_by_query({}):
            operations.append(
                UpdateOne({"_id": a["_id"]}, {'$set': {'i_trade': False}})
            )
        aco.bulk_write(operations)

    def add_gpt_meta(self, gpt_meta:Dict):
        meta = ACOGPTMeta(**{
            "product_name": gpt_meta["product_name"] if "product_name" in gpt_meta else None,
            "dosage": gpt_meta["dosage"] if "dosage" in gpt_meta else None,
            "dosage_form": gpt_meta["dosage_form"] if "dosage_form" in gpt_meta else None,
        })
        self.meta = meta
        self.processed = 2
        self.save()
        logger.info(f"got meta for {self.bezeichnung}")