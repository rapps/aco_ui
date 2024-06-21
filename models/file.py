from typing import Dict, Union

from bson import ObjectId
from pydantic import BaseModel
from pydantic_mongo import PydanticObjectId

import settings
from db.mongo import fs
logger = settings.logger

class ACOFile(BaseModel):
    id:str
    mimetype:str
    source:bytes

    def save(self) -> PydanticObjectId:
        try:
            _id =fs.put(self.source, id=self.id, mimetype=self.mimetype)
        except Exception as e:
            logger.info(f"existing file {self.id} do nothing")
            existing = ACOFile.get_objid(self.id)
            try:
                assert(existing != None)
            except AssertionError as ae:
                logger.exception(f"failed writing: {self.id} it is too big (probably)")
            return existing
        return _id

    @staticmethod
    def get_objid(id: str) -> Union[PydanticObjectId, None]:
        im = fs.find_one({"id": id})
        if im is None: return None
        return PydanticObjectId(im._id)

    @staticmethod
    def get_by_objid(id: PydanticObjectId) -> Union['ACOFile', None]:
        im = fs.find_one({"_id": id})
        if im is None: return None
        return ACOFile(id=im._file["id"], mimetype=im._file["mimetype"], source=im.read())

    @staticmethod
    def get(id:str) -> Union['ACOFile', None]:
        im = fs.find_one({"id": id})
        if im is None: return None
        return ACOFile(id=im._file["id"], mimetype=im._file["mimetype"], source=im.read())
