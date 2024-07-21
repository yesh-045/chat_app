from datetime import datetime
from json import dumps
from flask import jsonify
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, join_room, leave_room
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import request, redirect, url_for, render_template, flash
from db import get_user, save_user, save_room, add_room_members, get_rooms_for_user, get_room, is_room_member, \
    get_room_members, is_room_admin, update_room, remove_room_members, save_message, get_room_messages


app = Flask(__name__)
app.secret_key = "my secret key"
socketio = SocketIO(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

def get_db_connection():
    conn = psycopg2.connect(dbname="chat_app", user="yesh", password="chattheeye", host="localhost")
    return conn


@app.route('/')
def home():
    rooms = []
    if current_user.is_authenticated:
        rooms = get_rooms_for_user(current_user.username)
    return render_template("index.html", rooms=rooms)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password_input = request.form.get('password')
        user = get_user(username)

        if user and user.check_password(password_input):
            login_user(user)
            return redirect(url_for('home'))
        else:
            message = 'Failed to login!'
    return render_template('login.html', message=message)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')  # Default role is 'user'
        try:
            save_user(username, email, password, role)
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            message = "User already exists!"
    return render_template('signup.html', message=message)

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/create-room', methods=['GET', 'POST'])
@login_required
def create_room():
      
    
    message = ''
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        usernames = [username.strip() for username in request.form.get('members').split(',')]

        if len(room_name) and len(usernames):
            room_id = save_room(room_name, current_user.username)            
            add_room_members(room_id, room_name, usernames, current_user.username)
            return redirect(url_for('view_room', room_id=room_id))
        else:
            message = "Failed to create room"
    return render_template('create_room.html', message=message)


@app.route('/rooms')
@login_required
def rooms():
    conn = get_db_connection()
    cursor = conn.cursor()
    username = current_user.username  # Adjust this based on your user authentication setup
    cursor.execute("""
        SELECT DISTINCT r.id, r.name
        FROM rooms r
        LEFT JOIN room_members rm ON r.id = rm.room_id
        WHERE rm.username = %s OR r.created_by = %s
    """, (username, username))
    
    rooms = cursor.fetchall()
    conn.close()
    return render_template('rooms.html', rooms=rooms)



@app.route('/rooms/<room_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = get_room(room_id)
    if not room:
        flash('Room not found.', 'error')
        return redirect(url_for('index')) 
    if not is_room_admin(room_id, current_user.username):
        flash('You do not have permission to edit this room.', 'error')
        return redirect(url_for('view_room', room_id=room_id))
    
    room_members = get_room_members(room_id)
    if isinstance(room_members, list) and all(isinstance(member, dict) and 'username' in member for member in room_members):
            existing_room_members = [member['username'] for member in room_members]
    else:            
            existing_room_members = []            

    room_members_str = ",".join(existing_room_members)
   
    message = ''

    if request.method == 'POST':
        action_type = request.form.get('action_type')
        room_name = request.form.get('room_name')
        new_members = [username.strip() for username in request.form.get('members', '').split(',')]

        if action_type == 'edit':
            room['name'] = room_name
            update_room(room_id, room_name)
            message = 'Room details updated successfully.'

        members_to_add = list(set(new_members) - set(existing_room_members))
        members_to_remove = list(set(existing_room_members) - set(new_members))

        if action_type == 'add' and members_to_add:
            add_room_members(room_id, members_to_add, current_user.username)
            message = 'Members added successfully.'

        if action_type == 'remove' and members_to_remove:
            remove_room_members(room_id, members_to_remove)
            message = 'Members removed successfully.'

        flash(message, 'success')
        return redirect(url_for('view_room', room_id=room_id))

    return render_template('edit_room.html', room=room, room_members_str=room_members_str, message=message, room_id=room_id)

@app.route('/rooms/<int:room_id>')
@login_required
def view_room(room_id):
    print(f"Viewing room {room_id}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM rooms WHERE id = %s", (room_id,))
    room = cursor.fetchone()
    if not room:
        return "Room not found", 404

    cursor.execute("SELECT username FROM room_members WHERE room_id = %s", (room_id,))
    room_members = cursor.fetchall()

    cursor.execute("SELECT sender, text, created_at FROM messages WHERE room_id = %s ORDER BY created_at DESC LIMIT 100", (room_id,))
    messages = cursor.fetchall()

    conn.close()
    return render_template('view_room.html', username=current_user.username, room=room, room_members=room_members,
                               messages=messages,room_id=room_id)





@socketio.on('send_message')
def handle_send_message(data):
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
  
    app.logger.info(f"{username} has sent a message to the room: {message}")   

    save_message(room, message, username) 
    socketio.emit('receive_message', data, room=room)
@app.route('/get_room_messages/<room_id>')
def get_room_messages_route(room_id):
    messages = get_room_messages(room_id)
    messages_formatted = [{'sender': msg[0], 'text': msg[1], 'created_at': msg[2].strftime('%Y-%m-%d %H:%M:%S')} for msg in messages]
    return jsonify(messages_formatted)

@socketio.on('join_room')
def handle_join_room_event(data):
   
    app.logger.info("{} has joined the room {}".format(data.get('username', 'Unknown'), data.get('room', 'Unknown')))
    join_room(data['room'])
    socketio.emit('join_room_announcement', data, room=data['room'])


@socketio.on('leave_room')
def handle_leave_room_event(data):
    app.logger.info("{} has left the room {}".format(data['username'], data['room']))
    leave_room(data['room'])
    socketio.emit('leave_room_announcement', data, room=data['room'])


@login_manager.user_loader
def load_user(username):
    return get_user(username)


if __name__ == '__main__':
    socketio.run(app, debug=True)
