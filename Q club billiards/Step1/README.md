# Q Club Billiards Booking

A basic Flask project for an online pool table booking website.

## Features

- Flask routes for viewing tables and creating bookings
- SQLite database initialized automatically from `schema.sql`
- Booking records stored in `pool_bookings.db`
- Responsive HTML, CSS, and JavaScript frontend
- Basic duplicate booking prevention for the same table, date, and start time

## Project Structure

```text
.
+-- app.py
+-- database.py
+-- schema.sql
+-- requirements.txt
+-- templates/
|   +-- admin.html
|   +-- base.html
|   +-- booking.html
|   +-- confirmation.html
|   +-- index.html
+-- static/
    +-- css/
    |   +-- styles.css
    +-- js/
        +-- app.js
```

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

The SQLite database file is created automatically as `pool_bookings.db` when the app starts.
