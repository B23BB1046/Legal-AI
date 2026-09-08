import sqlite3
from pathlib import Path


class Database:

    def __init__(self):

        database_dir = Path(__file__).resolve().parent.parent / "database"
        database_dir.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(
            database_dir / "lexai.db",
            check_same_thread=False
        )

        self.cursor = self.connection.cursor()

        self.create_tables()

   
    # Create Tables
  

    def create_tables(self):

        self.cursor.execute("""

        CREATE TABLE IF NOT EXISTS users(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT,

            email TEXT,

            password TEXT

        )

        """)

        self.cursor.execute("""

        CREATE TABLE IF NOT EXISTS chat_history(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            question TEXT,

            answer TEXT

        )

        """)

        self.cursor.execute("""

        CREATE TABLE IF NOT EXISTS uploaded_files(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            filename TEXT

        )

        """)

        self.connection.commit()

   
    # Add User
   

    def add_user(self, username, email, password):

        self.cursor.execute(

            "INSERT INTO users(username,email,password) VALUES(?,?,?)",

            (username, email, password)

        )

        self.connection.commit()

    # Get User
   

    def get_user(self, email):

        self.cursor.execute(

            "SELECT * FROM users WHERE email=?",

            (email,)

        )

        return self.cursor.fetchone()

   
    # Save Chat
   

    def save_chat(self, question, answer):

        self.cursor.execute(

            "INSERT INTO chat_history(question,answer) VALUES(?,?)",

            (question, answer)

        )

        self.connection.commit()

   
    # Get Chat History
   

    def get_chat_history(self):

        self.cursor.execute(

            "SELECT * FROM chat_history ORDER BY id DESC LIMIT 50"

        )

        return self.cursor.fetchall()

   
    # Save Uploaded File
   

    def save_file(self, filename):

        self.cursor.execute(

            "INSERT INTO uploaded_files(filename) VALUES(?)",

            (filename,)

        )

        self.connection.commit()

   
    # Get Uploaded Files
 

    def get_uploaded_files(self):

        self.cursor.execute(

            "SELECT * FROM uploaded_files"

        )

        return self.cursor.fetchall()

    def delete_chat(self, chat_id):
        self.cursor.execute(
            "DELETE FROM chat_history WHERE id=?",
            (chat_id,),
        )
        self.connection.commit()
        return self.cursor.rowcount > 0