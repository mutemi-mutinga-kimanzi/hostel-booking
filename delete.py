import sqlite3

with sqlite3.connect('hostel.db') as conn:
    c = conn.cursor()
    c.execute("DELETE FROM bookings")
    c.execute("UPDATE rooms SET occupants = 0")
    conn.commit()

print("All bookings deleted and room occupancy reset.")
