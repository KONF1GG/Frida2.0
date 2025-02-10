import hashlib
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('distiluse-base-multilingual-cased-v1')


def clean_text(text):
    try:
        return text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    except UnicodeDecodeError:
        return text

def generate_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def generate_embedding(text):
    return model.encode(text)

