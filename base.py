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

    # Закрытие соединения
    def close(self):
        self.connection.close()
