import sqlite3


class SQL:
    def __init__(self, database):
        self.connection = sqlite3.connect(database)
        self.cursor = self.connection.cursor()

    # Добавление пользователя в БД
    def add_user(self, id):
        query = "INSERT INTO users (id) VALUES(?)"
        with self.connection:
            self.cursor.execute(query, (id,))
            self.connection.commit()

    # Проверка, есть ли пользователь в БД
    def user_exist(self, id):
        query = "SELECT * FROM users WHERE id = ?"
        with self.connection:
            result = self.cursor.execute(query, (id,)).fetchall()
            return bool(len(result))

    # Универсальные методы
    def get_field(self, table, id, field):
        query = f"SELECT {field} FROM {table} WHERE id = ?"
        with self.connection:
            result = self.cursor.execute(query, (id,)).fetchone()
            if result:
                return result[0]
            else:
                return None

    def update_field(self, table, id, field, value):
        query = f"UPDATE {table} SET {field} = ? WHERE id = ?"
        with self.connection:
            self.cursor.execute(query, (value, id))
            self.connection.commit()

    # Получить следующий доступный ID
    def get_next_available_id(self, table):
        query = f"SELECT MAX(id_dot) FROM {table}"
        with self.connection:
            result = self.cursor.execute(query).fetchone()
            max_id = result[0] if result[0] is not None else 0
            return max_id + 1

    # Таблица city_krasnoyarsk
    def add_dot_krasnoyarsk(self, name_dot, type_dot):
        # Сначала получаем следующий доступный ID
        next_id = self.get_next_available_id("city_krasnoyarsk")

        # Проверяем, является ли type_dot числом
        try:
            type_value = int(type_dot)
        except ValueError:
            type_value = type_dot

        query = "INSERT INTO city_krasnoyarsk (id_dot, name_dot, type_dot) VALUES(?, ?, ?)"
        with self.connection:
            self.cursor.execute(query, (next_id, name_dot, type_value))
            self.connection.commit()
            return next_id

    def get_dots(self, table, id_dot=None):
        if id_dot is None:
            query = f"SELECT * FROM {table}"
            with self.connection:
                return self.cursor.execute(query).fetchall()
        else:
            query = f"SELECT * FROM {table} WHERE id_dot = ?"
            with self.connection:
                return self.cursor.execute(query, (id_dot,)).fetchall()

    def get_id_dot_krasnoyarsk(self, name_dot):
        query = "SELECT id_dot FROM city_krasnoyarsk WHERE name_dot = ?"
        with self.connection:
            result = self.cursor.execute(query, (name_dot,)).fetchone()
            if result:
                return result[0]
            else:
                return None

    # Инициализация таблиц для фото, избранного и отзывов
    def init_tables(self):
        """Создает необходимые таблицы, если их нет"""
        # Таблица для избранного
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS favourites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                dot_id INTEGER NOT NULL,
                UNIQUE(user_id, dot_id)
            )
        """)
        
        # Таблица для отзывов
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                dot_id INTEGER NOT NULL,
                review_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Добавляем поле photo_id в city_krasnoyarsk, если его нет
        try:
            self.cursor.execute("ALTER TABLE city_krasnoyarsk ADD COLUMN photo_id TEXT")
        except:
            pass  # Колонка уже существует
        
        # Добавляем поле rating в reviews, если его нет
        try:
            self.cursor.execute("ALTER TABLE reviews ADD COLUMN rating INTEGER")
        except:
            pass  # Колонка уже существует
        
        # Добавление address
        try:
            self.cursor.execute("ALTER TABLE city_krasnoyarsk ADD COLUMN address TEXT")
        except:
            pass
        
        self.connection.commit()
    
    # Работа с фото мест
    def update_dot_photo(self, dot_id, photo_id):
        """Обновляет photo_id для места"""
        query = "UPDATE city_krasnoyarsk SET photo_id = ? WHERE id_dot = ?"
        with self.connection:
            self.cursor.execute(query, (photo_id, dot_id))
            self.connection.commit()
    
    def get_dot_photo(self, dot_id):
        """Получает photo_id места"""
        query = "SELECT photo_id FROM city_krasnoyarsk WHERE id_dot = ?"
        with self.connection:
            result = self.cursor.execute(query, (dot_id,)).fetchone()
            return result[0] if result and result[0] else None
    
    # Работа с избранным
    def add_to_favourites(self, user_id, dot_id):
        """Добавляет место в избранное пользователя"""
        query = "INSERT OR IGNORE INTO favourites (user_id, dot_id) VALUES(?, ?)"
        with self.connection:
            self.cursor.execute(query, (user_id, dot_id))
            self.connection.commit()
            return self.cursor.rowcount > 0
    
    def remove_from_favourites(self, user_id, dot_id):
        """Удаляет место из избранного пользователя"""
        query = "DELETE FROM favourites WHERE user_id = ? AND dot_id = ?"
        with self.connection:
            self.cursor.execute(query, (user_id, dot_id))
            self.connection.commit()
            return self.cursor.rowcount > 0
    
    def is_favourite(self, user_id, dot_id):
        """Проверяет, находится ли место в избранном"""
        query = "SELECT 1 FROM favourites WHERE user_id = ? AND dot_id = ?"
        with self.connection:
            result = self.cursor.execute(query, (user_id, dot_id)).fetchone()
            return bool(result)
    
    def get_favourite_dots(self, user_id):
        """Получает список избранных мест пользователя"""
        query = """
            SELECT d.* FROM city_krasnoyarsk d
            INNER JOIN favourites f ON d.id_dot = f.dot_id
            WHERE f.user_id = ?
        """
        with self.connection:
            return self.cursor.execute(query, (user_id,)).fetchall()
    
    # Работа с отзывами
    def add_review(self, user_id, dot_id, review_text, rating=None):
        """Добавляет отзыв о месте"""
        query = "INSERT INTO reviews (user_id, dot_id, review_text, rating) VALUES(?, ?, ?, ?)"
        with self.connection:
            self.cursor.execute(query, (user_id, dot_id, review_text, rating))
            self.connection.commit()
            return self.cursor.lastrowid
    
    def update_review_rating(self, review_id, rating):
        """Обновляет оценку в отзыве"""
        query = "UPDATE reviews SET rating = ? WHERE id = ?"
        with self.connection:
            self.cursor.execute(query, (rating, review_id))
            self.connection.commit()
    
    def get_dot_reviews(self, dot_id, limit=10):
        """Получает отзывы о месте"""
        query = "SELECT user_id, review_text, rating, created_at FROM reviews WHERE dot_id = ? ORDER BY created_at DESC LIMIT ?"
        with self.connection:
            return self.cursor.execute(query, (dot_id, limit)).fetchall()
    
    def get_review_by_user_dot(self, user_id, dot_id):
        """Получает отзыв пользователя о месте"""
        query = "SELECT id, review_text, rating FROM reviews WHERE user_id = ? AND dot_id = ?"
        with self.connection:
            return self.cursor.execute(query, (user_id, dot_id)).fetchone()
    
    def has_user_reviewed(self, user_id, dot_id):
        """Проверяет, оставил ли пользователь отзыв"""
        query = "SELECT 1 FROM reviews WHERE user_id = ? AND dot_id = ?"
        with self.connection:
            result = self.cursor.execute(query, (user_id, dot_id)).fetchone()
            return bool(result)
    
    def set_dot_address(self, id_dot, address):
        query = "UPDATE city_krasnoyarsk SET address = ? WHERE id_dot = ?"
        with self.connection:
            self.cursor.execute(query, (address, id_dot))
            self.connection.commit()
    def get_dot_address(self, id_dot):
        query = "SELECT address FROM city_krasnoyarsk WHERE id_dot = ?"
        with self.connection:
            r = self.cursor.execute(query, (id_dot,)).fetchone()
            return r[0] if r and r[0] else None
    
    # Закрытие соединения
    def close(self):
        self.connection.close()