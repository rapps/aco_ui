from collections import defaultdict
from typing import List, Dict


def group_object(in_list:List[Dict], attr:str):
    groups = defaultdict(list)

    for obj in in_list:
        groups[obj[attr]].append(obj)

    return groups