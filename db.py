import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash
from user import User

def get_db_connection():
    conn = psycopg2.connect(dbname="chat_app", user="yesh", password="chattheeye", host="localhost")
    return conn

def save_user(username, email, password, role='user'):
    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                       (username, email, password_hash, role))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_user(username):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user_data = cursor.fetchone()
        if user_data:
            return User(user_data['username'], user_data['email'], user_data['password'])
    finally:
        cursor.close()
        conn.close()
    return None

def save_room(room_name, created_by):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO rooms (name, created_by) VALUES (%s, %s) RETURNING id",
                       (room_name, created_by))
        room_id = cursor.fetchone()[0]
        conn.commit()
        return room_id
    finally:
        cursor.close()
        conn.close()

def add_room_members(room_id, room_name, usernames, added_by):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.executemany("INSERT INTO room_members (room_id, username, added_by) VALUES (%s, %s, %s)",
                           [(room_id, username, added_by) for username in usernames])
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_rooms_for_user(username):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT r.id, r.name
            FROM rooms r
            JOIN room_members rm ON r.id = rm.room_id
            WHERE rm.username = %s
        """, (username,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_room(room_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def is_room_member(room_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM room_members WHERE room_id = %s AND username = %s", (room_id, username))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()

def get_room_members(room_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT u.username FROM users u JOIN room_members rm ON u.username = rm.username WHERE rm.room_id = %s", (room_id,))
        members = cursor.fetchall()
        # Extract the username from each RealDictRow object
        return [member['username'] for member in members]
    finally:
        cursor.close()
        conn.close()

def is_room_admin(room_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM rooms WHERE id = %s AND created_by = %s", (room_id, username))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()

def update_room(room_id, room_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE rooms SET name = %s WHERE id = %s", (room_name, room_id))
        conn.commit()
    finally:
        return 0

def remove_room_members(room_id, usernames):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.executemany("DELETE FROM room_members WHERE room_id = %s AND username = %s",
                           [(room_id, username) for username in usernames])
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def save_message(room_id, message, sender):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO messages (room_id, text, sender) VALUES (%s, %s, %s)"
        cursor.execute(query, (room_id, message, sender))
        conn.commit()  # Commit the transaction to save the message
        print("Message saved to database: Room ID {}, Sender {}, Message {}".format(room_id, sender, message))
    except Exception as e:
        print("Failed to save message to database: {}".format(str(e)))
        if conn:
            conn.rollback()  # Rollback the transaction on error
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_room_messages(room_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT sender, text, created_at FROM messages WHERE room_id = %s ORDER BY created_at ASC', (room_id,))
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return messages
