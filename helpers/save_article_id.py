import re
def save_id_from_title(title:str) -> str:
    return re.sub(r"\s+", "_", "".join(i for i in title if ord(i)<128)).lower()
