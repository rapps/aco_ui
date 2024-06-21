import logging
from datetime import datetime

from pymongo import MongoClient, ASCENDING
import gridfs
import settings

logger = settings.logger

client = MongoClient(settings.MONGO_ENDPOINT)
db = client.aco
sis = db["sis"]
oeaz_pdf = db["oeaz_pdf"]
oeaz_structured = db["oeaz_structured"]
oeaz_article = db["oeaz_article"]
oeaz_mesh = db["oeaz_mesh"]
fs = gridfs.GridFS(db)

sis.create_index([('id', 1)], unique=True)
oeaz_pdf.create_index([('id', 1)], unique=True)
oeaz_structured.create_index([('id', 1)], unique=True)
oeaz_article.create_index([('id', 1)], unique=True)
oeaz_mesh.create_index([('id', 1)], unique=True)
db.fs.files.create_index([('id', 1)], unique=True)

class LongSessionCursor():
    def __init__(self, collection, query) -> None:
        self.client = MongoClient()
        self.session = client.start_session()
        self.sessionId = self.session.session_id
        self.collection = collection
        self.cursor = collection.find(query, no_cursor_timeout=True)
        self.refresh_timestamp = datetime.now()

    def iter(self):
        try:
            for document in self.cursor:
                if (datetime.now() - self.refresh_timestamp).total_seconds() > 300:
                    logger.info("refreshing session")
                    self.session.client.admin.command({"refreshSessions": [self.sessionId]})
                    self.refresh_timestamp = datetime.now()
                yield document
            return None
        except Exception as e:
            logger.error(e, exc_info=True)
        finally:
            self.cursor.close()

    def close_cursor(self):
        try:self.cursor.close()
        except:pass