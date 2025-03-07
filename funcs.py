import hashlib
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('distiluse-base-multilingual-cased-v1')
# model = whisperx.load_model("large-v3", 'cpu', compute_type='float32', language='ru')

def clean_text(text):
    try:
        return text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    except UnicodeDecodeError:
        return text

def generate_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def generate_embedding(text):
    return model.encode(text)


# async def transcribe_audio(file_data) -> str:
#     temp_file_path = file_data 

#     try:
#         y, sr = librosa.load(temp_file_path, sr=None)
#         print("Аудио загружено:", type(y), y.shape)

#         result = model.transcribe(y)
#         print("Результат транскрипции:", result)

#         if isinstance(result, dict) and 'text' in result:
#             text = result['text']
#             print("Текст из результата:", text[:10])  
#             return text
#         else:
#             print("Результат транскрипции не содержит поля 'text'.")
#             return ""

#     except Exception as e:
#         print(f"Произошла ошибка при транскрипции: {str(e)}")
#         return "" 
