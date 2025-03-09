from typing import List
import mysql.connector
import psycopg2
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections
from sklearn.preprocessing import normalize
from pymilvus import utility
import funcs
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType
from pymilvus.exceptions import MilvusException

from scheme import VectorWikiData


class MySQL:
    def __init__(self, host, port, user, password, database) -> None:
        self.conn = mysql.connector.connect(
                host=host,  
                port=port,             
                user=user,
                password=password, 
                database=database  
            )
        self.cursor = self.conn.cursor()  

    def connection_close(self):
        self.conn.close()
        self.conn.close()

    def get_pages_data(self):
        self.cursor.execute("""
        select DISTINCT p.name, p.text, b.slug, p.slug, c.name 
        from pages p  
        join books b on p.book_id = b.id  
        left join chapters c on p.chapter_id = c.id 
        join bookshelves_books bb on bb.book_id = b.id  
        where bb.bookshelf_id not in (1, 10) and p.`text` <> ''
        """)
        return self.cursor.fetchall()


class PostgreSQL:
    def __init__(self, host, port, user, password, database) -> None:
        self.connection = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        self.cursor = self.connection.cursor()

    def insert_new_topic(self, hash, title, text, user_id):
        # Вставка в таблицу frida_storage
        query = '''
            INSERT INTO frida_storage (hash, title, text, isexstra)
            VALUES (%s, %s, %s, %s)
        '''
        
        self.cursor.execute(query, (hash, title, text, True))
        
        # Вставка в таблицу exstraTopics
        exstra_query = '''
            INSERT INTO exstraTopics (hash, user_id)
            VALUES (%s, %s)
        '''
        
        self.cursor.execute(exstra_query, (hash, user_id))
        
        # Фиксация изменений в базе данных
        self.connection.commit()    
    def add_user_to_db(self, user_id: int, username: str, first_name: str, last_name: str):
        query = '''
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
        '''
        
        self.cursor.execute(query, (user_id, username, first_name, last_name))
        
        self.connection.commit()

    def log_message(self, user_id, user_query, response, topic_hashs: List[str]):
        query = '''
            INSERT INTO bot_logs (user_id, query, response)
            VALUES (%s, %s, %s)
            RETURNING log_id;
        '''
        
        self.cursor.execute(query, (user_id, user_query, response))
        
        log_id = self.cursor.fetchone()[0]
        
        for topic_hash in topic_hashs:
            hash_query = '''
                INSERT INTO bot_log_topic_hashes (log_id, topic_hash)
                VALUES (%s, %s)
            '''
            self.cursor.execute(hash_query, (log_id, topic_hash))
        
        self.connection.commit()

    def user_exists(self, user_id: int):
        query = '''
            SELECT 1 FROM users WHERE user_id = %s
        '''
        self.cursor.execute(query, (user_id, ))

        result = self.cursor.fetchone()

        return result is not None
    
    def check_user_is_admin(self, user_id):
        query = '''
            SELECT is_admin FROM users WHERE user_id = %s
        '''
        self.cursor.execute(query, (user_id, ))

        result = self.cursor.fetchone()
        return result[0]
    
    def get_admins(self):
        query = '''
            SELECT user_id, username FROM users WHERE is_admin = TRUE;
        '''
        self.cursor.execute(query)

        result = self.cursor.fetchall()
        return result
    
    def get_data_for_vector_db(self):
        query = "select hash, book_name, title, text from frida_storage"
        
        self.cursor.execute(query)

        result = self.cursor.fetchall()
        return result
    
    def get_history(self, user_id):
        query = '''
        WITH LastThreeLogs AS (
            SELECT *
            FROM bot_logs bl
            WHERE bl.user_id = %s
            ORDER BY bl.created_at DESC
            LIMIT 3
        )
        SELECT *
        FROM LastThreeLogs
        ORDER BY created_at ASC;
        '''
        
        self.cursor.execute(query, (user_id, ))

        result = self.cursor.fetchall()
        return result
    
    def get_items_by_hashs(self, hashs: tuple[str], user_id):
        # Generate placeholders for each item in the hashs tuple
        placeholders = ', '.join(['%s'] * len(hashs))
        
        query = f'''
        SELECT book_name, text, url
        FROM frida_storage fs
        WHERE fs.hash IN (
            SELECT DISTINCT blth.topic_hash
            FROM bot_log_topic_hashes blth
            JOIN bot_logs bl ON blth.log_id = bl.log_id
            WHERE bl.log_id IN (
                SELECT bl.log_id
                FROM bot_logs bl
                WHERE bl.user_id = %s
                ORDER BY bl.created_at DESC
                LIMIT 3
            )
            UNION
            SELECT %s
        )
        AND fs.hash IN ({placeholders});
        '''
        params = (user_id, hashs[0], *hashs)

        self.cursor.execute(query, params)

        result = self.cursor.fetchall()
        return result

    
    def delete_items_by_hashs(self, hashs: set[str]):

        hashs = tuple(hashs)
        query = '''
            DELETE FROM frida_storage WHERE hash in %s 
        '''
        self.cursor.execute(query, (hashs,))

        self.connection.commit()
        affected_rows = self.cursor.rowcount
        return affected_rows
    
    def get_count(self):
        query = '''
            select COUNT(*) from frida_storage fs2 
        '''
        self.cursor.execute(query)
        result = self.cursor.fetchone()
        return result[0]

    def connection_close(self):
        self.cursor.close()
        self.connection.close()


class Milvus:
    def __init__(self, host, port, collection_name):
        connections.connect("default", host=host, port=port)

        self.collection_name = collection_name

        self.fields = [
            FieldSchema(name='hash', dtype=DataType.VARCHAR, is_primary=True, max_length=255),
            FieldSchema(name='embedding', dtype=DataType.FLOAT_VECTOR, dim=512),
            FieldSchema(name='embeddingTitleLess', dtype=DataType.FLOAT_VECTOR, dim=512) 
        ]

        self.index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 300}
        }

        self.schema = CollectionSchema(fields=self.fields, description="WIKI")

        collections = utility.list_collections()

        if collection_name in collections:
            self.collection = Collection(self.collection_name)
            if self.collection.num_entities > 0:
                self.collection.load()
        else:
            self.collection = Collection(name=self.collection_name, schema=self.schema)

        self.search_params = {"metric_type": "COSINE", "params": {"ef": 200, "nprobe": 10}}

    def create_index(self):
        self.collection.create_index(field_name='embedding', index_params=self.index_params)
        self.collection.create_index(field_name='embeddingTitleLess', index_params=self.index_params)

        self.collection.load()
        self.collection.flush()


    def init_collection(self):
        try:
            collections = utility.list_collections()
            if self.collection.name in collections:
                collection = Collection(self.collection_name)
                collection.drop()
                print(f"Коллекция {self.collection_name} была удалена.")

            self.collection = Collection(name=self.collection_name, schema=self.schema)
            print(f"Коллекция {self.collection_name} была создана")

        except MilvusException as e:
            print(f"Ошибка при проверке или удалении коллекции: {e}")

    def insert_data(self, data: List[VectorWikiData]):
        hashs, embeddings, embeddingsTitleLess = [], [], []

        for topic in data:
            hashs.append(topic.hash)
            embeddings.append(funcs.generate_embedding(topic.text))
            embeddingsTitleLess.append(funcs.generate_embedding(topic.textTitleLess))

        embeddings = normalize(embeddings, axis=1)
        embeddingsTitleLess = normalize(embeddingsTitleLess, axis=1)
        
        self.collection.insert([hashs, embeddings, embeddingsTitleLess])

        self.create_index()


    def search(self, query_text):
        query_embedding = funcs.generate_embedding(query_text)
        query_embedding = normalize([query_embedding], axis=1)

        results = self.collection.search(
            data=query_embedding,
            anns_field="embedding",
            param=self.search_params,
            limit=3,
        )

        return results
    
    def clean_similar_vectors(self, similarity_threshold: float = 1):
        all_vectors = self.collection.query(expr='hash != "0"', output_fields=["embeddingTitleLess"])
        
        vectors = [item['embeddingTitleLess'] for item in all_vectors]
        ids = [item['hash'] for item in all_vectors]
        deleted_ids = set()  

        for i, query_vector in enumerate(vectors):
            if ids[i] in deleted_ids:
                continue
            search_results = self.collection.search(
                data=[query_vector], 
                anns_field="embeddingTitleLess",
                param={"metric_type": "COSINE", "params": {"ef": 200, "nprobe": 10}},
                limit=3
            )
            
            for result in search_results[0]:
                similarity = result.distance 
                
                if similarity >= similarity_threshold and result.id != ids[i]:
                    deleted_ids.add(result.id)
                    self.collection.delete(expr=f"hash == '{result.id}'")
                    print(f"Удален вектор с ID: {result.id} с похожестью на {ids[i]} {similarity * 100:.2f}%")
        self.collection.flush()
        self.collection.load()
        return deleted_ids


    def get_data_count(self):
        return self.collection.num_entities

    def drop_collection(self):
        self.collection.drop()

    def connection_close(self):
        connections.disconnect("default")

    



