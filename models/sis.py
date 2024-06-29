from typing import Union, List, Dict, Generator

from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

import settings
from db.mongo import sis, LongSessionCursor

logger = settings.logger

class Indication(BaseModel):
    code:str
    name:str
    synonym:Union[List[str],None]=None
    parentCode:Union[str,None]
    children:List['Indication']=[]

    @staticmethod
    def from_sis_dict(**kwargs):
        synonyme = [s for s in  kwargs["IndicationSynonym"] if s != kwargs["IndicationName"]]
        return Indication(
            code=kwargs["IndicationCode"],
            name=kwargs["IndicationName"],
            synonym=synonyme,
            parentCode= None if kwargs["IndicationParentCode"] == "" else kwargs["IndicationParentCode"]
        )

    @staticmethod


    @staticmethod
    def from_sis_dict_list(data:List[Dict[str,Union[str,int,List[str]]]]) -> Dict[str,'Indication']:
        indication_dict:Dict[str,Indication] = {d["IndicationCode"]:Indication.from_sis_dict(**d)  for d in data}
        idx = 1
        for value in indication_dict.values():
            #logger.info(idx)
            idx += 1
            node:Indication = value
            for k, v in indication_dict.items():
                if node.parentCode == k and not node == v:
                    v.children.append(node)

        return indication_dict


class SISMeta(BaseModel):
    id:str
    bezeichnung:str
    # aco_productname:Union[str|None]=None
    # aco_packagename:Union[str|None]=None
    # product_name:Union[str|None] = None
    # dosage:Union[str|None] = None
    # dosage_form:Union[str|None] = None
    # assign_confidence:float=0.0
    eu_zlnumm:Union[str|None] = None
    i_trade:bool
    znumm:int
    pzn:List[int] = []
    indications:List[Indication] = []
    pi:bool=False
    faulty:bool=False

    @staticmethod
    def from_sis_dict(data:Dict, indication_dict=Dict[str,Indication], exclude_fringe=True) -> Union['SISMeta', None]:
        b_lang = data.get("BezeichnungLang", None)
        if b_lang is not None and b_lang.strip() == "": b_lang = None
        e_zlnumm = data.get("EUZLNUMM", None)
        if e_zlnumm is not None and e_zlnumm.strip() == "": e_zlnumm = None
        faulty=False

        bezeichnung = data.get("Bezeichnung", None)
        bezeichnung_lang = b_lang
        if b_lang: bezeichnung = bezeichnung_lang
        eu_zlnumm = e_zlnumm
        znumm = data.get("ZNUMM", None)
        i_trade = data.get("WVZdata", None)
        id_ = data.get("ZLNUMM", None)
        pi = data.get("isPrallelimport", False)
        pzns = []
        for pzn in data["PhzNr"]:
            pzns.append(int(pzn))
        indications = []
        for ind in data["IndicationGroups"]:
            indications.append(indication_dict[ind])

        if id_.startswith("07"):
            pi = True
        if id_ == "999999" or id_ == "999990": #Verweis
            faulty = True
        if exclude_fringe and (faulty or pi or not i_trade): return None

        return SISMeta(
            bezeichnung=bezeichnung,
            eu_zlnumm=eu_zlnumm,
            i_trade=i_trade,
            id=id_,
            znumm=znumm, #? not pzn
            pzn = pzns,
            indications=indications,
            pi=pi,
            faulty=faulty
        )

    @staticmethod
    def get(id: int) -> Union['OeazPdfIssue', None]:
        entry = sis.find_one({"id": id})
        if entry is None: return None
        return SISMeta(**entry)

    @staticmethod
    def get_dicts_by_query(query: Dict) -> Generator:
        lsc = LongSessionCursor(sis, query)
        return lsc.iter()

    def save(self) -> 'SISMeta':
        try:
             sis.insert_one(self.dict())
        except DuplicateKeyError as e:
             query = {"id": self.id}
             newvalues = {"$set": self.dict()}
             sis.update_one(query, newvalues)
        except Exception as eg:
             logger.exception("Something wrong with the save")
        return self

