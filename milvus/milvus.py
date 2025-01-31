from pymilvus import MilvusClient, DataType, model, connections
from sentence_transformers import SentenceTransformer


class MilvusDatabase:
    def __init__(self, milvus_host, collection_name="Frida_storage", dimension=384):
        """Инициализация подключения к Milvus."""
        self.client = MilvusClient(milvus_host) 
        self.collection_name = collection_name
        self.dimension = dimension
        self.model = SentenceTransformer('distiluse-base-multilingual-cased-v1')
        self.sentence_transformer_ef = model.dense.SentenceTransformerEmbeddingFunction(
            model_name='distiluse-base-multilingual-cased-v1', device='cpu'
        )

        self.schema = {
            "auto_id": False,
            "enable_dynamic_field": True,
            "fields": [
                {"name": "id", "type": DataType.INT64, "is_primary": True},
                {"name": "vector", "type": DataType.FLOAT_VECTOR, "dim": self.dimension},
                {"name": "text", "type": DataType.VARCHAR, "max_length": 512}
            ]
        }

    def init_collection(self):
        """Создает коллекцию в Milvus."""
        if not self.client.has_collection(self.collection_name):
            self.client.create_collection(self.collection_name, self.schema)
            print(f"Коллекция '{self.collection_name}' была успешно создана.")
        else:
            print(f"Коллекция '{self.collection_name}' уже существует.")

    def delete_collection(self):
        """Удаляет коллекцию в Milvus, если она существует."""
        if self.client.has_collection(self.collection_name):
            self.client.drop_collection(self.collection_name)
            print(f"Коллекция '{self.collection_name}' была удалена.")
        else:
            print(f"Коллекция '{self.collection_name}' не существует.")

    def generate_embedding(self, text):
        """Генерирует эмбеддинг для переданного текста."""
        return self.model.encode(text)

    def insert_data(self, data):
        """Вставляет данные (эмбеддинги) в коллекцию Milvus."""
        embeddings = [self.generate_embedding(text) for text in data]
        # Формируем данные для вставки в коллекцию
        insert_data = [{"id": i, "vector": embeddings[i].tolist(), "text": data[i]} for i in range(len(data))]
        self.client.insert(collection_name=self.collection_name, data=insert_data)
        num_entities = self.client.num_entities(collection_name=self.collection_name)
        print(f"Данные успешно вставлены. Общее количество сущностей: {num_entities}")
        return num_entities

    def get_collection_info(self):
        """Возвращает информацию о коллекции."""
        return self.client.describe_collection(self.collection_name)

    def create_index(self):
        """Создает индекс для коллекции."""
        index_params = {
            "index_type": "AUTOINDEX",
            "metric_type": "COSINE",
            "params": {}
        }
        self.client.create_index(self.collection_name, "vector", index_params)
        print(f"Индекс для коллекции '{self.collection_name}' был успешно создан.")

    def load_collection(self):
        """Загружает коллекцию в память."""
        self.client.load_collection(self.collection_name)
        print(f"Коллекция '{self.collection_name}' загружена.")

    def search(self, query):
        """Выполняет векторный поиск в коллекции."""
        query_embedding = self.model.encode([query]) 
        res = self.client.search(
            collection_name=self.collection_name,
            data=query_embedding,
            limit=1,
            output_fields=["text"]
        )
        return res


if __name__ == "__main__":
    # Инициализация Milvus базы данных
    milvus_db = MilvusDatabase(milvus_host="./milvus_demo.db")

    # Инициализация коллекции
    milvus_db.init_collection()

    # Пример данных для вставки
    sample_data = [
        "Пример текста для встраивания",
        "Другой пример текста",
        "Какой смысл в векторных представлениях?"
    ]
    milvus_db.insert_data(sample_data)

    # Создание индекса
    milvus_db.create_index()

    # Получение информации о коллекции
    collection_info = milvus_db.get_collection_info()
    print(collection_info)

    # Поиск по запросу
    query = "Что такое векторные представления?"
    search_results = milvus_db.search(query)
    print("Результаты поиска:", search_results)
