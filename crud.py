import re
import config
from databases import Milvus, MySQL, PostgreSQL
import funcs
from scheme import Page, VectorWikiData

def insert_wiki_data():
    try:
        mysql_db = MySQL(**config.mysql_config)
        pages = mysql_db.get_pages_data()
    except Exception as e:
        print(f"Ошибка при подключении к MySQL или получении данных: {e}")
        return
    finally:
        if 'mysql_db' in locals():
            mysql_db.connection_close()

    if not pages:
        print("Не удалось получить данные из MySQL.")
        return

    try:
        postgres_db = PostgreSQL(**config.postgres_config)

        postgres_db.cursor.execute(
            "DELETE FROM frida_storage WHERE isExstra != TRUE;"
        )

        for page in pages:
            page_model = Page(title=page[0], text=page[1].strip(), book_slug=page[2], page_slug=page[3], book_name=page[4] if page[4] else '')
            url = f'http://wiki.freedom1.ru:8080/books/{page_model.book_slug}/page/{page_model.page_slug}'
            page_model.text = re.sub(r'(\r\n)+', '\r\n', page_model.text)
            page_hash = funcs.generate_hash(page_model.text)
            if len(page_model.text) < 20:
                continue


            clean_text_value = funcs.clean_text(page_model.text)

            try:
                postgres_db.cursor.execute(
                    """
                    INSERT INTO frida_storage (hash, book_name, title, text, url)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (hash) DO NOTHING;
                    """,
                    (page_hash, page_model.book_name, page_model.title, clean_text_value, url)
                )

            except Exception as e:
                print(f"Ошибка при вставке данных для страницы {page_model.title}: {e}")
                continue 

        postgres_db.connection.commit()
        return True

    except Exception as e:
        print(f"Ошибка при обработке данных в PostgreSQL: {e}")
        if 'postgres_db' in locals():
            postgres_db.connection.rollback()

    finally:
        if 'postgres_db' in locals():
            postgres_db.connection_close()


def     insert_all_data_from_postgres_to_milvus():
    postgres_db = PostgreSQL(**config.postgres_config)
    milvus_db = Milvus(config.MILVUS_HOST, config.MILVUS_PORT, 'Frida_bot_data')
    milvus_db.init_collection()

    data = postgres_db.get_data_for_vector_db()
    data_list = []
    for topic in data:
        hash = topic[0]
        book_name = topic[1] if topic[1] else ''
        title = topic[2]
        textTitleLess = topic[3]
        text = book_name + '\n' + title + textTitleLess
        data_list.append(VectorWikiData(hash=hash, text=text, textTitleLess=textTitleLess))
    milvus_db.insert_data(data_list)
    milvus_db.create_index()
    duplicates = milvus_db.clean_similar_vectors()
    deleted_count = 0
    if duplicates:
        deleted_count = postgres_db.delete_items_by_hashs(duplicates)
    data_count = postgres_db.get_count()
    postgres_db.connection_close()
    milvus_db.connection_close()
    return data_count, deleted_count

def add_new_topic(title, text, user_id):
    try:
        postgres_db = PostgreSQL(**config.postgres_config)
        text_hash = funcs.generate_hash(text)
        postgres_db.insert_new_topic(text_hash, title, text, user_id)
        milvus_db = Milvus(config.MILVUS_HOST, config.MILVUS_PORT, 'Frida_bot_data')
        milvus_db.insert_data([VectorWikiData(hash=text_hash, text=title+text, textTitleLess=text)])
        milvus_db.collection.flush()
        milvus_db.collection.load()
        postgres_db.connection_close()
        milvus_db.connection_close()
        return True
    except Exception as e:
        return e




# insert_wiki_data()
# insert_all_data_from_postgres_to_milvus()