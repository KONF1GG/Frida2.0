import config
import mysql.connector

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

    def get_data_all(self):
        self.cursor.execute("select DISTINCT p.id, p.name, p.text from pages p  join books b on p.book_id = b.id  join bookshelves_books bb on bb.book_id = b.id  where bb.bookshelf_id in (2, 3, 4, 5, 6, 7, 8, 9) and p.`text` <> ''")
        return self.cursor.fetchall()
    
class PostgreSQL:
    def __init__(self) -> None:
        pass

    