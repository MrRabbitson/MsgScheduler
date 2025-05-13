import sqlite3
from datetime import datetime
import json

class SQL:
    def __init__(self, database):
        self.connection = sqlite3.connect(database)
        self.cursor = self.connection.cursor()
        self._create_tables()

    def _create_tables(self):
        """Создает таблицы в базе данных, если они не существуют"""
        # Таблица пользователей
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                support_status INTEGER DEFAULT 0,
                support_target_user INTEGER DEFAULT NULL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER PRIMARY KEY,
                current_state TEXT,
                platform TEXT,
                message_type TEXT,
                text TEXT,
                original_text TEXT,
                time TEXT,
                date TEXT,
                chat_id TEXT,
                webhook TEXT,
                image_file_id TEXT,
                feedback BOOLEAN DEFAULT 0,
                feedback_button_text TEXT,
                feedback_creator_id INTEGER,
                feedback_reply_user_id INTEGER,
                buttons TEXT,
                selected_days TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Таблица для сообщений Telegram
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_user INTEGER NOT NULL,
                id_chat TEXT NOT NULL,
                msg TEXT NOT NULL,
                name_user TEXT NOT NULL,
                time TEXT NOT NULL,
                date TEXT,
                image TEXT,
                buttons TEXT,
                onMondays INTEGER DEFAULT 0,
                onTuesdays INTEGER DEFAULT 0,
                onWednesdays INTEGER DEFAULT 0,
                onThursdays INTEGER DEFAULT 0,
                onFridays INTEGER DEFAULT 0,
                onSaturdays INTEGER DEFAULT 0,
                onSundays INTEGER DEFAULT 0,
                FOREIGN KEY (id_user) REFERENCES users(id)
            )
        """)

        # Таблица для сообщений Discord
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS discord (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_user INTEGER NOT NULL,
                webhook TEXT NOT NULL,
                msg TEXT NOT NULL,
                name_user TEXT NOT NULL,
                time TEXT NOT NULL,
                date TEXT,
                image TEXT,
                buttons TEXT,
                onMondays INTEGER DEFAULT 0,
                onTuesdays INTEGER DEFAULT 0,
                onWednesdays INTEGER DEFAULT 0,
                onThursdays INTEGER DEFAULT 0,
                onFridays INTEGER DEFAULT 0,
                onSaturdays INTEGER DEFAULT 0,
                onSundays INTEGER DEFAULT 0,
                FOREIGN KEY (id_user) REFERENCES users(id)
            )
        """)
        self.connection.commit()

    def add_user(self, user_id, name):
        """Добавляет нового пользователя"""
        with self.connection:
            return self.cursor.execute("INSERT OR IGNORE INTO users (id, name) VALUES(?, ?)",
                                     (user_id, name))

    def user_exists(self, user_id):
        """Проверяет существование пользователя"""
        with self.connection:
            result = self.cursor.execute("SELECT 1 FROM users WHERE id = ?",
                                       (user_id,)).fetchone()
            return bool(result)

    def get_field(self, table, user_id, field):
        """Получает значение поля из таблицы"""
        with self.connection:
            result = self.cursor.execute(f"SELECT {field} FROM {table} WHERE id = ?",
                                       (user_id,)).fetchone()
            return result[0] if result else None

    def update_field(self, table, user_id, field, value):
        """Обновляет значение поля в таблице"""
        with self.connection:
            return self.cursor.execute(f"UPDATE {table} SET {field} = ? WHERE id = ?",
                                     (value, user_id))

    def add_msg_telegram(self, id_user, id_chat, msg, name_user, time, date,
                         onMondays, onTuesdays, onWednesdays, onThursdays,
                         onFridays, onSaturdays, onSundays, image=None, buttons=None):
        """Добавляет сообщение для Telegram"""
        query = """
            INSERT INTO telegram (
                id_user, id_chat, msg, name_user, time, date, image, buttons,
                onMondays, onTuesdays, onWednesdays, onThursdays, 
                onFridays, onSaturdays, onSundays
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.connection:
            return self.cursor.execute(query, (
                id_user, id_chat, msg, name_user, time, date, image, json.dumps(buttons) if buttons else None,
                onMondays, onTuesdays, onWednesdays, onThursdays,
                onFridays, onSaturdays, onSundays
            ))

    def get_telegram_messages_to_send(self):
        """Получает сообщения Telegram, готовые к отправке"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%d.%m.%Y")
        weekday = now.weekday()

        query = """
            SELECT id, id_chat, msg, image, buttons FROM telegram 
            WHERE (date = ? AND time = ?) 
            OR (time = ? AND (
                (onMondays = 1 AND ? = 0) OR
                (onTuesdays = 1 AND ? = 1) OR
                (onWednesdays = 1 AND ? = 2) OR
                (onThursdays = 1 AND ? = 3) OR
                (onFridays = 1 AND ? = 4) OR
                (onSaturdays = 1 AND ? = 5) OR
                (onSundays = 1 AND ? = 6)
            ))
        """
        with self.connection:
            results = self.cursor.execute(query, (
                current_date, current_time, current_time,
                weekday, weekday, weekday, weekday,
                weekday, weekday, weekday
            )).fetchall()

            return [{
                'id': row[0],
                'chat_id': row[1],
                'text': row[2],
                'image': row[3],
                'buttons': json.loads(row[4]) if row[4] else None
            } for row in results]

    def delete_telegram_message(self, msg_id):
        """Удаляет сообщение Telegram по ID"""
        with self.connection:
            return self.cursor.execute("DELETE FROM telegram WHERE id = ?", (msg_id,))

    def add_msg_discord(self, id_user, webhook, msg, name_user, time, date,
                        onMondays, onTuesdays, onWednesdays, onThursdays,
                        onFridays, onSaturdays, onSundays, image=None, buttons=None):
        """Добавляет сообщение для Discord"""
        query = """
            INSERT INTO discord (
                id_user, webhook, msg, name_user, time, date, image, buttons,
                onMondays, onTuesdays, onWednesdays, onThursdays, 
                onFridays, onSaturdays, onSundays
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.connection:
            return self.cursor.execute(query, (
                id_user, webhook, msg, name_user, time, date, image, json.dumps(buttons) if buttons else None,
                onMondays, onTuesdays, onWednesdays, onThursdays,
                onFridays, onSaturdays, onSundays
            ))

    def get_discord_messages_to_send(self):
        """Получает сообщения Discord, готовые к отправке"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%d.%m.%Y")
        weekday = now.weekday()

        query = """
            SELECT id, webhook, msg, image, buttons FROM discord 
            WHERE (date = ? AND time = ?) 
            OR (time = ? AND (
                (onMondays = 1 AND ? = 0) OR
                (onTuesdays = 1 AND ? = 1) OR
                (onWednesdays = 1 AND ? = 2) OR
                (onThursdays = 1 AND ? = 3) OR
                (onFridays = 1 AND ? = 4) OR
                (onSaturdays = 1 AND ? = 5) OR
                (onSundays = 1 AND ? = 6)
            ))
        """
        with self.connection:
            results = self.cursor.execute(query, (
                current_date, current_time, current_time,
                weekday, weekday, weekday, weekday,
                weekday, weekday, weekday
            )).fetchall()

            return [{
                'id': row[0],
                'webhook': row[1],
                'text': row[2],
                'image': row[3],
                'buttons': json.loads(row[4]) if row[4] else None
            } for row in results]

    def delete_discord_message(self, msg_id):
        """Удаляет сообщение Discord по ID"""
        with self.connection:
            return self.cursor.execute("DELETE FROM discord WHERE id = ?", (msg_id,))

    def get_user_telegram_messages(self, user_id):
        query = "SELECT * FROM telegram WHERE id_user = ?"
        with self.connection:
            results = self.cursor.execute(query, (user_id,)).fetchall()
            return [{
                'id': row[0],
                'chat_id': row[2],
                'text': row[3],
                'time': row[5],
                'date': row[6],
                'image': row[7],
                'buttons': row[8],
                'onMondays': row[9],
                'onTuesdays': row[10],
                'onWednesdays': row[11],
                'onThursdays': row[12],
                'onFridays': row[13],
                'onSaturdays': row[14],
                'onSundays': row[15]
            } for row in results]

    def get_user_discord_messages(self, user_id):

        query = "SELECT * FROM discord WHERE id_user = ?"
        with self.connection:
            results = self.cursor.execute(query, (user_id,)).fetchall()
            return [{
                'id': row[0],
                'webhook': row[2],
                'text': row[3],
                'time': row[5],
                'date': row[6],
                'image': row[7],
                'buttons': row[8],
                'onMondays': row[9],
                'onTuesdays': row[10],
                'onWednesdays': row[11],
                'onThursdays': row[12],
                'onFridays': row[13],
                'onSaturdays': row[14],
                'onSundays': row[15]
            } for row in results]

    def init_user_data(self, user_id):
        """Инициализирует запись для хранения данных пользователя"""
        with self.connection:
            self.cursor.execute(
                "INSERT OR IGNORE INTO user_data (user_id) VALUES (?)",
                (user_id,)
            )

    def update_user_data(self, user_id, **fields):
        """Обновляет данные пользователя"""
        self.init_user_data(user_id)
        set_clause = ", ".join([f"{field} = ?" for field in fields.keys()])
        values = list(fields.values())
        values.append(user_id)

        with self.connection:
            self.cursor.execute(
                f"UPDATE user_data SET {set_clause} WHERE user_id = ?",
                values
            )

    def get_user_data(self, user_id):
        """Получает все данные пользователя"""
        self.init_user_data(user_id)
        with self.connection:
            result = self.cursor.execute(
                "SELECT * FROM user_data WHERE user_id = ?",
                (user_id,)
            ).fetchone()

            if result:
                columns = [column[0] for column in self.cursor.description]
                return dict(zip(columns, result))
            return None

    def get_active_sessions(self):
        """Получает список активных сессий пользователей"""
        with self.connection:
            return self.cursor.execute(
                "SELECT user_id, current_state FROM user_data WHERE current_state IS NOT NULL"
            ).fetchall()
    def clear_user_data(self, user_id):
        """Очищает данные пользователя"""
        with self.connection:
            self.cursor.execute(
                "UPDATE user_data SET current_state = NULL, platform = NULL, "
                "message_type = NULL, text = NULL, original_text = NULL, "
                "time = NULL, date = NULL, chat_id = NULL, webhook = NULL, "
                "image_file_id = NULL, feedback = 0, feedback_button_text = NULL, "
                "feedback_creator_id = NULL, feedback_reply_user_id = NULL, "
                "buttons = NULL, selected_days = NULL WHERE user_id = ?",
                (user_id,)
            )

    def delete_user_data(self, user_id):
        """Удаляет данные пользователя"""
        with self.connection:
            self.cursor.execute(
                "DELETE FROM user_data WHERE user_id = ?",
                (user_id,)
            )
    def close(self):
        """Закрывает соединение с базой данных"""
        self.connection.close()