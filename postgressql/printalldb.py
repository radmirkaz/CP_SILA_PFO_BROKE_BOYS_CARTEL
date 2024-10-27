import psycopg2

# Параметры для подключения к базе данных PostgreSQL
DB_USER = "imagineuser"
DB_PASSWORD = "FT-EB9r2z55622M1b"
DB_NAME = "brokeboyscartel"
DB_HOST = "83.166.236.254"

# Подключаемся к базе данных
conn = psycopg2.connect(
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST
)
cursor = conn.cursor()

# Функция для вывода всех записей из таблицы 'likes'
def print_all_likes():
    cursor.execute("SELECT * FROM likes")
    rows = cursor.fetchall() 
    for row in rows:
        print(row) 

print_all_likes()
