from datetime import datetime, time
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import DATABASE, get_db_connection, init_db


app = Flask(__name__)
app.config["SECRET_KEY"] = "*"
app.config["DATABASE"] = DATABASE
BOOKING_STATUSES = ("Pending", "Confirmed", "Cancelled")
OPENING_MINUTES = 14 * 60
CLOSING_MINUTES = (24 * 60) + 30
MIN_DURATION = 0.5
MAX_DURATION = 6


def format_duration(value):
    duration = float(value)
    if duration == 0.5:
        return "30 minutes"
    if duration.is_integer():
        hours = int(duration)
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    return f"{duration:g} hours"


app.jinja_env.filters["format_duration"] = format_duration


def parse_time_to_minutes(value):
    parsed_time = datetime.strptime(value, "%H:%M").time()
    minutes = parsed_time.hour * 60 + parsed_time.minute
    if parsed_time == time(0, 0):
        return 24 * 60
    return minutes


def is_booking_within_business_hours(start_time, duration):
    start_minutes = parse_time_to_minutes(start_time)
    end_minutes = start_minutes + int(duration * 60)
    return OPENING_MINUTES <= start_minutes <= (24 * 60) and end_minutes <= CLOSING_MINUTES


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            flash("Admin access is required.", "error")
            return redirect(url_for("my_bookings"))
        return view(*args, **kwargs)

    return wrapped_view


@app.before_request
def ensure_database():
    init_db(app.config["DATABASE"])
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection(app.config["DATABASE"])
        g.user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not all([full_name, email, phone, password]):
            flash("Please complete every registration field.", "error")
            return redirect(url_for("register"))

        conn = get_db_connection(app.config["DATABASE"])
        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if existing_user:
            conn.close()
            flash("An account with that email already exists.", "error")
            return redirect(url_for("register"))

        cursor = conn.execute(
            """
            INSERT INTO users (full_name, email, phone, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, 'player', ?)
            """,
            (
                full_name,
                email,
                phone,
                generate_password_hash(password),
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        session.clear()
        session["user_id"] = cursor.lastrowid
        conn.close()

        flash("Account created. You are now logged in.", "success")
        return redirect(url_for("booking"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection(app.config["DATABASE"])
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        flash("Logged in successfully.", "success")
        if user["role"] == "admin":
            return redirect(url_for("admin"))
        return redirect(url_for("booking"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/")
def index():
    conn = get_db_connection(app.config["DATABASE"])
    tables = conn.execute(
        """
        SELECT * FROM tables
        WHERE status = 'available'
        ORDER BY hourly_rate, type, name
        """
    ).fetchall()
    featured_bookings = conn.execute(
        """
        SELECT bookings.*, tables.name AS table_name, tables.hourly_rate
        FROM bookings
        JOIN tables ON bookings.table_id = tables.id
        ORDER BY booking_date, start_time
        LIMIT 4
        """
    ).fetchall()
    conn.close()

    return render_template("index.html", tables=tables, bookings=featured_bookings)


@app.route("/booking")
@login_required
def booking():
    conn = get_db_connection(app.config["DATABASE"])
    table_types = conn.execute(
        """
        SELECT type, MIN(hourly_rate) AS hourly_rate, COUNT(*) AS table_count
        FROM tables
        WHERE status = 'available'
        GROUP BY type
        ORDER BY hourly_rate, type
        """
    ).fetchall()
    conn.close()

    booking_times = []
    for minutes in range(OPENING_MINUTES, (24 * 60) + 1, 30):
        hour = minutes // 60
        minute = minutes % 60
        value = "00:00" if hour == 24 else f"{hour:02d}:{minute:02d}"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        period = "AM" if hour == 24 else "PM"
        booking_times.append((value, f"{display_hour}:{minute:02d} {period}"))

    durations = [duration / 2 for duration in range(1, int(MAX_DURATION * 2) + 1)]

    return render_template(
        "booking.html",
        table_types=table_types,
        booking_times=booking_times,
        durations=durations,
    )


@app.route("/admin")
@admin_required
def admin():
    conn = get_db_connection(app.config["DATABASE"])
    tables = conn.execute(
        "SELECT * FROM tables ORDER BY status, name"
    ).fetchall()
    users = conn.execute(
        "SELECT id, full_name, email, phone, role, created_at FROM users ORDER BY role, full_name"
    ).fetchall()
    bookings = conn.execute(
        """
        SELECT bookings.*, tables.name AS table_name, tables.type AS table_type,
               tables.hourly_rate, users.full_name AS account_name
        FROM bookings
        JOIN tables ON bookings.table_id = tables.id
        LEFT JOIN users ON bookings.user_id = users.id
        ORDER BY booking_date DESC, start_time DESC
        """
    ).fetchall()
    total_revenue = sum(
        booking["duration"] * booking["hourly_rate"]
        for booking in bookings
        if booking["status"] != "Cancelled"
    )
    conn.close()

    return render_template(
        "admin.html",
        tables=tables,
        users=users,
        bookings=bookings,
        booking_statuses=BOOKING_STATUSES,
        total_revenue=total_revenue,
    )


@app.route("/admin/bookings/<int:booking_id>/status", methods=["POST"])
@admin_required
def update_booking_status(booking_id):
    status = request.form.get("status", "").strip()

    if status not in BOOKING_STATUSES:
        flash("Please choose a valid booking status.", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection(app.config["DATABASE"])
    cursor = conn.execute(
        "UPDATE bookings SET status = ? WHERE id = ?",
        (status, booking_id),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        flash("Booking not found.", "error")
    else:
        flash("Booking status updated.", "success")

    return redirect(url_for("admin"))


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@admin_required
def update_user_role(user_id):
    role = request.form.get("role", "").strip()
    if role not in ("admin", "player"):
        flash("Please choose a valid user role.", "error")
        return redirect(url_for("admin"))
    if user_id == g.user["id"] and role != "admin":
        flash("You cannot remove your own admin access.", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection(app.config["DATABASE"])
    cursor = conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()

    flash("User role updated." if cursor.rowcount else "User not found.", "success" if cursor.rowcount else "error")
    return redirect(url_for("admin"))


@app.route("/admin/tables/<int:table_id>/status", methods=["POST"])
@admin_required
def update_table_status(table_id):
    status = request.form.get("status", "").strip().lower()
    if status not in ("available", "maintenance", "retired"):
        flash("Please choose a valid table status.", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection(app.config["DATABASE"])
    cursor = conn.execute("UPDATE tables SET status = ? WHERE id = ?", (status, table_id))
    conn.commit()
    conn.close()

    flash("Table status updated." if cursor.rowcount else "Table not found.", "success" if cursor.rowcount else "error")
    return redirect(url_for("admin"))


@app.route("/book", methods=["POST"])
@login_required
def create_booking():
    customer_name = g.user["full_name"]
    email = g.user["email"]
    phone = g.user["phone"] or request.form.get("phone", "").strip()
    table_type = request.form.get("table_type", "").strip()
    booking_date = request.form.get("booking_date", "").strip()
    start_time = request.form.get("start_time", "").strip()
    duration = request.form.get("duration", "").strip()

    if not all([customer_name, email, phone, table_type, booking_date, start_time, duration]):
        flash("Please complete every booking field.", "error")
        return redirect(url_for("booking"))

    try:
        duration_value = float(duration)
        if (
            duration_value < MIN_DURATION
            or duration_value > MAX_DURATION
            or not (duration_value * 2).is_integer()
        ):
            raise ValueError
    except ValueError:
        flash("Duration must be between 30 minutes and 6 hours.", "error")
        return redirect(url_for("booking"))

    try:
        if not is_booking_within_business_hours(start_time, duration_value):
            flash("Bookings must start between 2:00 PM and 12:00 AM and finish by 12:30 AM.", "error")
            return redirect(url_for("booking"))
    except ValueError:
        flash("Please choose a valid booking time.", "error")
        return redirect(url_for("booking"))

    conn = get_db_connection(app.config["DATABASE"])
    selected_table = conn.execute(
        """
        SELECT tables.id
        FROM tables
        WHERE tables.type = ?
          AND tables.status = 'available'
          AND NOT EXISTS (
              SELECT 1
              FROM bookings
              WHERE bookings.table_id = tables.id
                AND bookings.booking_date = ?
                AND bookings.start_time = ?
                AND bookings.status != 'Cancelled'
          )
        ORDER BY tables.hourly_rate, tables.name
        LIMIT 1
        """,
        (table_type, booking_date, start_time),
    ).fetchone()

    if selected_table is None:
        conn.close()
        flash("No tables of that type are available at the selected time.", "error")
        return redirect(url_for("booking"))

    cursor = conn.execute(
        """
        INSERT INTO bookings (
            user_id, customer_name, email, phone, table_id, booking_date,
            start_time, duration, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.user["id"],
            customer_name,
            email,
            phone,
            selected_table["id"],
            booking_date,
            start_time,
            duration_value,
            "Pending",
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return redirect(url_for("confirmation", booking_id=booking_id))


@app.route("/confirmation/<int:booking_id>")
@login_required
def confirmation(booking_id):
    conn = get_db_connection(app.config["DATABASE"])
    if g.user["role"] == "admin":
        owner_clause = ""
        params = (booking_id,)
    else:
        owner_clause = "AND bookings.user_id = ?"
        params = (booking_id, g.user["id"])

    booking_record = conn.execute(
        f"""
        SELECT bookings.*, tables.name AS table_name, tables.type AS table_type,
               tables.hourly_rate
        FROM bookings
        JOIN tables ON bookings.table_id = tables.id
        WHERE bookings.id = ?
        {owner_clause}
        """,
        params,
    ).fetchone()
    conn.close()

    if booking_record is None:
        flash("Booking not found.", "error")
        return redirect(url_for("booking"))

    total_price = booking_record["duration"] * booking_record["hourly_rate"]
    return render_template(
        "confirmation.html",
        booking=booking_record,
        total_price=total_price,
    )


@app.route("/my-bookings")
@login_required
def my_bookings():
    conn = get_db_connection(app.config["DATABASE"])
    bookings = conn.execute(
        """
        SELECT bookings.*, tables.name AS table_name, tables.type AS table_type,
               tables.hourly_rate
        FROM bookings
        JOIN tables ON bookings.table_id = tables.id
        WHERE bookings.user_id = ?
        ORDER BY booking_date DESC, start_time DESC
        """,
        (g.user["id"],),
    ).fetchall()
    conn.close()

    return render_template("my_bookings.html", bookings=bookings)


@app.route("/my-bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel_my_booking(booking_id):
    conn = get_db_connection(app.config["DATABASE"])
    cursor = conn.execute(
        """
        UPDATE bookings
        SET status = 'Cancelled'
        WHERE id = ? AND user_id = ? AND status != 'Cancelled'
        """,
        (booking_id, g.user["id"]),
    )
    conn.commit()
    conn.close()

    flash("Booking cancelled." if cursor.rowcount else "Booking could not be cancelled.", "success" if cursor.rowcount else "error")
    return redirect(url_for("my_bookings"))


if __name__ == "__main__":
    app.run(debug=True)
