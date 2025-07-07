from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_very_secret_key'

# Ensure database and tables exist
def init_db():
    with sqlite3.connect('hostel.db') as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gender TEXT NOT NULL,
                block TEXT NOT NULL,
                room_no INTEGER NOT NULL,
                occupants INTEGER DEFAULT 0
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                block TEXT NOT NULL,
                room_no INTEGER NOT NULL
            )
        ''')

        # Create 4 blocks (A–D), 5 rooms per block, for each gender
        for gender in ['boys', 'girls']:
            for block in ['A', 'B', 'C', 'D']:
                for room_no in range(1, 6):
                    c.execute('''SELECT * FROM rooms WHERE gender=? AND block=? AND room_no=?''',
                              (gender, block, room_no))
                    if not c.fetchone():
                        c.execute('INSERT INTO rooms (gender, block, room_no) VALUES (?, ?, ?)',
                                  (gender, block, room_no))
        conn.commit()
       
       
init_db()

@app.route('/status')
def status_page():
    if 'user' not in session:
        return redirect(url_for('sign_page'))
    return render_template('status.html')

@app.route('/api/status')
def booking_status_api():
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 403

    name = session['user']['username']
    conn = get_db_connection()
    booking = conn.execute('SELECT * FROM bookings WHERE name = ?', (name,)).fetchone()
    conn.close()

    if booking:
        return jsonify({'status': 'approved', 'booking': dict(booking)})
    else:
        return jsonify({'status': 'rejected'})


def get_db_connection():
    conn = sqlite3.connect('hostel.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/delete/<int:booking_id>')
def delete_booking(booking_id):
    if 'user' not in session or session['user']['role'] != 'admin':
        return "Unauthorized", 403

    conn = get_db_connection()
    booking = conn.execute('SELECT gender, block, room_no FROM bookings WHERE id = ?', (booking_id,)).fetchone()

    if booking:
        gender = booking['gender']
        block = booking['block']
        room_no = booking['room_no']

        conn.execute('''
            UPDATE rooms
            SET occupants = occupants - 1
            WHERE gender = ? AND block = ? AND room_no = ? AND occupants > 0
        ''', (gender, block, room_no))

        conn.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
        conn.commit()

    conn.close()
    return redirect(url_for('view_bookings'))




@app.route('/edit/<int:booking_id>')
def edit_booking(booking_id):
     print("Session:", session)
     if 'user' not in session or session['user']['role'] != 'admin':
        print("Unauthorized access.")
        return "Unauthorized", 403

     conn = get_db_connection()
     booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
     conn.close()
     return render_template('edit.html', booking=booking)


@app.route('/update/<int:booking_id>', methods=['POST'])
def update_booking(booking_id):
    if 'user' not in session or session['user']['role'] != 'admin':
        return "Unauthorized", 403

    name = request.form['name']
    gender = request.form['gender']
    block = request.form['block']
    room_no = request.form['room_no']

    conn = get_db_connection()
    conn.execute('''
        UPDATE bookings
        SET name = ?, gender = ?, block = ?, room_no = ?
        WHERE id = ?
    ''', (name, gender, block, room_no, booking_id))
    conn.commit()
    conn.close()

    return redirect(url_for('view_bookings'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('sign_page'))



@app.route('/users')
def view_users():
    with sqlite3.connect('hostel.db') as conn:
        c = conn.cursor()
        c.execute("SELECT username, email, role FROM users")
        users = c.fetchall()
    return render_template('users.html', users=users)


@app.route('/bookings')
def view_bookings():
    with sqlite3.connect('hostel.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, gender, block, room_no FROM bookings")
        bookings = c.fetchall()
    return render_template('bookings.html', bookings=bookings, session=session)

@app.route('/admin/clear_bookings', methods=['POST'])
def clear_bookings():
    if 'user' not in session or session['user']['role'] != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    with sqlite3.connect('hostel.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM bookings")
        c.execute("UPDATE rooms SET occupants = 0")
        conn.commit()

    return jsonify({"status": "success", "message": "All bookings cleared and rooms reset."})


@app.route('/')
def sign_page():
    return render_template('sign.html')
@app.route('/sign.html')
def sign_page_html():
    return render_template('sign.html')


# Book page
@app.route('/book')
def book_page():
    return render_template('book.html')

# API to fetch available rooms
@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    gender = request.args.get('gender')
    block = request.args.get('block')
    with sqlite3.connect('hostel.db') as conn:
        c = conn.cursor()
        c.execute('''SELECT room_no, occupants FROM rooms WHERE gender=? AND block=?''',
                  (gender, block))
        rooms = [{'room_no': row[0], 'occupants': row[1]} for row in c.fetchall()]
        return jsonify(rooms)

# API to book a room
@app.route('/api/book', methods=['POST'])
def book_room():
    data = request.json
    name = data['name']
    gender = data['gender']
    block = data['block']
    room_no = data['room_no']

    with sqlite3.connect('hostel.db') as conn:
        c = conn.cursor()

        c.execute("SELECT * FROM bookings WHERE name = ?", (name,))
        if c.fetchone():
            return jsonify({"status": "error", "message": "You have already booked a room."})

        c.execute('''SELECT occupants FROM rooms WHERE gender=? AND block=? AND room_no=?''',
                  (gender, block, room_no))
        result = c.fetchone()

        if result and result[0] < 4:
            c.execute('''UPDATE rooms SET occupants = occupants + 1 WHERE gender=? AND block=? AND room_no=?''',
                      (gender, block, room_no))
            c.execute('''INSERT INTO bookings (name, gender, block, room_no) VALUES (?, ?, ?, ?)''',
                      (name, gender, block, room_no))
            conn.commit()
            return jsonify({"status": "success", "message": "Room booked!"})
        else:
            return jsonify({"status": "error", "message": "Room is full."})


# Signup route
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    role = data.get('role')
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    try:
        with sqlite3.connect('hostel.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (role, username, email, password) VALUES (?, ?, ?, ?)",
                           (role, username, email, password))
            conn.commit()
            session['user'] = {'username': username, 'role': role}
            return jsonify({"status": "success", "redirect": "/home.html"})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Username already exists."})


@app.route('/home.html')
def home():
    if 'user' not in session:
        return redirect(url_for('sign_page'))  # ✅ Fixed here
    return render_template('home.html', user=session['user'])

@app.route('/debug_session')
def debug_session():
    return jsonify(dict(session))


@app.route('/log.html')
def login_page():
    return render_template('log.html')

# Login route
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    role = data.get('role', '').lower()
    username = data.get('username')
    password = data.get('password')

    # Admin login block
    if role == 'admin':
        if username.lower() == "admin" and password == "Kmtc@admin":
            session['user'] = {'username': 'admin', 'role': 'admin'}
            return jsonify({'status': 'success', 'redirect': '/vieww.html'})
        else:
            return jsonify({'status': 'fail', 'message': 'Invalid admin credentials'})

    # Normal user login block (this runs only if role is not 'admin')
    with sqlite3.connect('hostel.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?",
                       (username, password, role))
        user = cursor.fetchone()

        if user:
            session['user'] = {'username': username, 'role': role}
            return jsonify({'status': 'success', 'redirect': '/home.html'})
        else:
            return jsonify({'status': 'fail', 'message': 'Invalid credentials'})

@app.route('/vieww.html')
def admin_page():
    return render_template('vieww.html')
# Admin view
@app.route('/vieww')
def admin_view():
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect(url_for('sign_page'))  # or dashboard if you define it

    with sqlite3.connect('hostel.db') as conn:
        c = conn.cursor()
        c.execute("SELECT username, email FROM users")
        users = c.fetchall()

        c.execute("SELECT COUNT(*) FROM rooms")
        total_rooms = c.fetchone()[0] * 4
        c.execute("SELECT SUM(occupants) FROM rooms")
        occupied = c.fetchone()[0] or 0
        status = "Full" if occupied >= total_rooms else "Vacant"

    return render_template('vieww.html', users=users, status=status)


# Launch app
if __name__ == '__main__':
    import webbrowser
    webbrowser.open_new("http://127.0.0.1:5000")
    app.run(debug=True)
