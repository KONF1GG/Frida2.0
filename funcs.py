import torch
from unidecode import unidecode
from transformers import AutoTokenizer, AutoModel
import hashlib
from torch import Tensor
import logging
from contextlib import contextmanager
import gc
# 
# model_base_path = "/root/.cache/huggingface/hub/models--intfloat--multilingual-e5-large/snapshots/0dc5580a448e4284468b8909bae50fa925907bc5"
model_base_path = 'C:\\Users\\krokx\\.cache\\huggingface\\hub\\models--intfloat--multilingual-e5-large\\snapshots\\0dc5580a448e4284468b8909bae50fa925907bc5'

model = AutoModel.from_pretrained(model_base_path)
tokenizer = AutoTokenizer.from_pretrained(model_base_path)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
logging.warning(device)
# model = model.to(device)

@contextmanager
def use_device(model, device):
    original_device = next(model.parameters()).device
    if original_device != device:
        model.to(device)
    try:
        yield
    finally:
        if original_device != device:
            model.to(original_device)

def average_pool(last_hidden_states: Tensor,
                 attention_mask: Tensor) -> Tensor:
    last_hidden = last_hidden_states.masked_fill(~attention_mask[..., None].bool(), 0.0)
    return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

def clean_text(text):
    try:
        return text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    except UnicodeDecodeError:
        return text

def generate_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def generate_embedding(texts):
    batch_dict = tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
    batch_dict = {key: value.to(device) for key, value in batch_dict.items()}
    outputs = model(**batch_dict)
    embeddings = average_pool(outputs.last_hidden_state, batch_dict['attention_mask'])

    embeddings = embeddings.detach().cpu().numpy()
    return embeddings

def normalize_text(text):
    normalized_text = unidecode(text)
    return normalized_text.strip()

def clear_gpu_memory():
    """Очистка видеопамяти."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()
