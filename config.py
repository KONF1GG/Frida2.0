import os
from dotenv import dotenv_values

dotenv_values()

TOKEN = os.getenv('TOKEN')
API_KEY=os.getenv('API_KEY')
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
# MILVUS_HOST = 'localhost'
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")


HOST_MYSQL= os.getenv('HOST_MYSQL')
PORT_MYSQL= os.getenv('PORT_MYSQL')
USER_MYSQL= os.getenv('USER_MYSQL')
PASSWORD_MYSQL= os.getenv('PASSWORD_MYSQL')
DB_MYSQL= os.getenv('DB_MYSQL')

POSTGRES_USER=os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD=os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB=os.getenv('POSTGRES_DB')

mysql_config = {
    'host': HOST_MYSQL,
    'port': PORT_MYSQL,
    'user': USER_MYSQL,
    'password': PASSWORD_MYSQL,
    'database': DB_MYSQL
}

postgres_config = {
    'host': 'frida_db',
    'port': 5432,
    'user': POSTGRES_USER,
    'password': POSTGRES_PASSWORD,
    'database': POSTGRES_DB
}

loading_sticker = "CAACAgIAAxkBAAJMS2YHPrVKVmiyNhVR3J5vQE2Qpu-kAAIjAAMoD2oUJ1El54wgpAY0BA"

WHISPER_API  = os.getenv('WHISPER_API')