import json
import random
import re
from pprint import pprint
from typing import Dict

from elasticsearch import Elasticsearch

import settings
from helpers.group import group_object
from models.aco import ACOMeta
from models.oeaz_structured import OeazArticle

logger = settings.logger


class Client:
    def __init__(self):
        self.es = Elasticsearch(settings.ELASTIC)
        client_info = self.es.info()
        print('Connected to Elasticsearch!')
        pprint(client_info.body)

def index_oeaz(_client: Client, query:Dict):
    _client.es.indices.delete(index="oeaz_products", ignore_unavailable=True)
    _client.es.indices.delete(index="oeaz_substances", ignore_unavailable=True)
    _client.es.indices.delete(index="oeaz_diseases", ignore_unavailable=True)
    _client.es.indices.create(index="oeaz_products", mappings={})  # todo:mappings!
    _client.es.indices.create(index="oeaz_substances", mappings={})  # todo:mappings!
    _client.es.indices.create(index="oeaz_diseases", mappings={})  # todo:mappings!
    articles = [OeazArticle(**a) for a in OeazArticle.get_dicts_by_query(query)]
    operations_products = []
    operations_substances = []
    operations_diseases = []
    for idx, article in enumerate(articles):
        logger.info(f"[{idx}/{len(articles)}] - checked")
        prod = [{"id": article.id, "product": kw.name} for kw in article.meta.keywords if kw.type == "trade_name"]
        subs = [{"id": article.id, "substance": kw.name} for kw in article.meta.keywords if kw.type == "substance"]
        dis = [{"id": article.id, "disease": kw.name} for kw in article.meta.keywords if kw.type == "disease"]
        for entry in prod:
            operations_products.append({'index': {'_index': "oeaz_products"}})
            operations_products.append(entry)
        for entry in subs:
            operations_substances.append({'index': {'_index': "oeaz_substances"}})
            operations_substances.append(entry)
        for entry in dis:
            operations_diseases.append({'index': {'_index': "oeaz_diseases"}})
            operations_diseases.append(entry)

    if len(operations_products) >= 0:
        _client.es.bulk(operations=operations_products)
        operations_products.clear()
    if len(operations_substances) >= 0:
        _client.es.bulk(operations=operations_substances)
        operations_substances.clear()
    if len(operations_diseases) >= 0:
        _client.es.bulk(operations=operations_diseases)
        operations_substances.clear()

def index_aco(_client: Client, query:Dict):
    _client.es.indices.delete(index="aco", ignore_unavailable=True)
    _client.es.indices.delete(index="aco_actives", ignore_unavailable=True)
    _client.es.indices.create(index="aco", mappings={})  # todo:mappings!
    _client.es.indices.create(index="aco_actives", mappings={})  # todo:mappings!
    aco_dicts = list(ACOMeta.get_dicts_by_query(query))
    operations_aco = []
    operations_actives = []
    for aco in aco_dicts:
        aco = ACOMeta(**aco)

        ws = [{"id": aco.id, "bezeichnung": v.bezeichnung} for v in aco.wirkstoffe]

        for entry in ws:
            operations_actives.append({'index': {'_index': "aco_actives"}})
            operations_actives.append(entry)

        try:
            index_obj = {
                "id": aco.id,
                "bezeichnung": aco.bezeichnung,
                "anwendung": " ".join([kt.text for kt in aco.kurztexte if kt.bezeichnung=='Anwendungsgebiete']),
                "warn": " ".join([kt.text for kt in aco.kurztexte if kt.bezeichnung in ['Gegenanzeigen', 'Wechselwirkungen', 'Warnhinweise'] and kt.text is not None])
            }
        except:
            print()

        operations_aco.append({'index': {'_index': "aco"}})
        operations_aco.append(index_obj)
    _client.es.bulk(operations=operations_aco)
    _client.es.bulk(operations=operations_actives)

def check_mapping(_client: Client, index_name: str) -> Dict:
    mapping = _client.es.indices.get_mapping(index=index_name)
    return mapping.raw[index_name]


def reindex_oeaz_aco():
    _client = Client()
    index_aco(_client=_client, query={"processed": 2})
    index_oeaz(_client=_client, query = {"rubrik": {"$regex": ".*Tara.*", '$options': 'i'}, "processed" : 2})


def search_aco_wirkstoff(_client:Client, query):
    op = _client.es.search(
        index="aco_actives",
        query={
            "query_string": {
                "fields": ["bezeichnung"],
                'query': f'*{query.replace(" ", "*")}*' #todo: needs love
            }
        },
        source_includes=["id", "bezeichnung"]
    )
    result = []
    for hit in op.raw['hits']["hits"]:
        result.append({
            "aco": ACOMeta.get(hit["_source"]["id"]),
            "active": hit["_source"]["bezeichnung"],
            "score": hit["_score"]
        })
    result = [{"wirkstoff": k, "aco":v} for k,v in group_object(result, "active").items()]
    return result

def search_aco_bezeichnung(query):
    op = _client.es.search(
        index="aco",
        query={
            "query_string": {
                "fields": ["bezeichnung"],
                'query': f'*{query.replace(" ", "*")}*'  # todo: needs love
            }
        },
        source_includes=["id", "bezeichnung"]
    )
    result = []
    for hit in op.raw['hits']["hits"]:
        result.append({
            "name": hit["_source"]["bezeichnung"],
            "id": hit["_source"]["id"]
            #"score": hit["_score"]
        })
    return result

def search_oeaz_bezeichnung(query):
    result = []
    query = f"*{re.sub('^[^a-zA-ZäöüÄÖÜß]+','*', query)}*"
    op = _client.es.search(
        index="oeaz_products",
        query={
            "query_string": {
                "fields": ["product"],
                'query': query #todo: needs love
            }
        },
        source_includes=["id", "product", "title"]
    )
    for hit in op.raw['hits']["hits"]:
        result.append({
            "name": hit["_source"]["product"] + " - " + hit["_source"]["title"],
            "id": hit["_source"]["id"],
            "score": hit["_score"]
        })

    wirkstoffe = re.sub('^[^a-zA-ZäöüÄÖÜß ]+',"*", query)
    op = _client.es.search(
        index="oeaz_substances",
        query={
            "query_string": {
                "fields": ["substance"],
                'query': query #todo: needs love
            }
        },
        source_includes=["id", "substance", "title"]
    )
    for hit in op.raw['hits']["hits"]:
        result.append({
            "name": hit["_source"]["substance"] + " - " + hit["_source"]["title"],
            "id": hit["_source"]["id"],
            "score": hit["_score"]
        })

    disease = re.sub('^[^a-zA-ZäöüÄÖÜß ]+',"*", query)
    op = _client.es.search(
        index="oeaz_diseases",
        query={
            "query_string": {
                "fields": ["disease"],
                'query': query #todo: needs love
            }
        },
        source_includes=["id", "disease", "title"]
    )
    for hit in op.raw['hits']["hits"]:
        result.append({
            "name": hit["_source"]["disease"] + " - " + hit["_source"]["title"],
            "id": hit["_source"]["id"],
            "score": hit["_score"]
        })
    logger.info(f"size: {len(result)}")
    return result

def search_articles(_client:Client, aco:ACOMeta):
    #search in products
    result = {
        "product": [],
        "substance": [],
        "disease": []
    }
    bezeichnung = re.sub('^[^a-zA-ZäöüÄÖÜß ]+',"*", aco.bezeichnung)
    logger.info(f"product: {bezeichnung}")
    op = _client.es.search(
        index="oeaz_products",
        query={
            "query_string": {
                "fields": ["product"],
                'query': f'{bezeichnung}' #todo: needs love
            }
        },
        source_includes=["id", "product"]
    )
    for hit in op.raw['hits']["hits"]:
        result["product"].append({
            "article": OeazArticle.get(hit["_source"]["id"]),
            "product": hit["_source"]["product"],
            "score": hit["_score"]
        })

    wirkstoffe = " ".join([re.sub('^[^a-zA-ZäöüÄÖÜß ]+',"*", ws.bezeichnung) for ws in aco.wirkstoffe])
    logger.info(f"wirkstoffe: {wirkstoffe}")
    op = _client.es.search(
        index="oeaz_substances",
        query={
            "query_string": {
                "fields": ["substance"],
                'query': wirkstoffe #todo: needs love
            }
        },
        source_includes=["id", "substance"]
    )
    for hit in op.raw['hits']["hits"]:
        result["substance"].append({
            "article": OeazArticle.get(hit["_source"]["id"]),
            "substance": hit["_source"]["substance"],
            "score": hit["_score"]
        })

    disease = " ".join([re.sub('^[^a-zA-ZäöüÄÖÜß ]+',"*", kt.text) for kt in aco.kurztexte if kt.bezeichnung=='Anwendungsgebiete'])
    logger.info(f"disease: {disease}")
    op = _client.es.search(
        index="oeaz_diseases",
        query={
            "query_string": {
                "fields": ["disease"],
                'query': disease #todo: needs love
            }
        },
        source_includes=["id", "disease"]
    )
    for hit in op.raw['hits']["hits"]:
        result["disease"].append({
            "article": OeazArticle.get(hit["_source"]["id"]),
            "disease": hit["_source"]["disease"],
            "score": hit["_score"]
        })
    return result

def test_articles_for_aco(aco:ACOMeta):
    test2 = search_articles(_client=_client, aco=aco)
    print(f'Test was for query -{aco.bezeichnung}-')
    print(f'ws: {[ws.bezeichnung for ws in aco.wirkstoffe]}')
    print(f'aw: {[kt.text for kt in aco.kurztexte if kt.bezeichnung=="Anwendungsgebiete"]}')
    for cat, val in test2.items():
        print(f"{cat}:")
        for entry in val:
            print(f'[{entry["score"]}] {entry[cat]}: {entry["article"].title}')


_client = Client()


#search_oeaz_bezeichnung("dep")