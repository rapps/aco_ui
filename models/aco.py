from typing import Union, Any, Dict, List, Tuple, Generator

from pydantic import BaseModel
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

class ACOMeta(SISMeta):
    wirkstoffe: List[ACOActive]
    kurztexte: List[ACOKurztext]
    packungen:List[ACOPackage]

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
        lsc = LongSessionCursor(sis, query)
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
    def get_name_groups(substring_len:int) -> list[Any]:
        return  list(aco.aggregate([
            {"$sort": {"bezeichnung": 1}},
            {"$group":
                {
                    "_id": {"$substrCP": ['$bezeichnung', 0, 2], },
                    "products": {"$push": {"bezeichnung": '$bezeichnung', "id": "$id"}}

                }
            },
            {"$sort": {"_id": 1}},
        ]))
    @staticmethod
    def get_by_name_groups():
        test = ACOMeta.get_name_groups(2)
        tree_list = []
        for entry in test:
            sb_node = {
                "text": entry["_id"],
                "icon": "fa fa-inbox fa-fw",
                "nodes": []
            }
            tree_list.append(sb_node)
            for product in entry["products"]:
                p_node = {
                    "text": product["bezeichnung"],
                    "icon": "fa fa-inbox fa-fw",
                    "class": "text-info",
                    "href": f"/aco/{product['id']}/"
                }
                sb_node["nodes"].append(p_node)

        return tree_list

