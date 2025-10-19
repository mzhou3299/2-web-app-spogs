import os
from datetime import datetime, date
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, jsonify, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
app = Flask(__name__)
client = MongoClient(
    os.getenv("MONGO_URI"),
    username=os.getenv("MONGO_USER"),
    password=os.getenv("MONGO_PASS"),
)
db = client["homeworkdb"]
col = db["assignments"]
users_col = db["users"]  # New collection for users


def serialize(doc):
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", ""),
        "course": doc.get("course", ""),
        "notes": doc.get("notes", ""),
        "due_date": (
            doc.get("due_date").strftime("%Y-%m-%d")
            if isinstance(doc.get("due_date"), (datetime, date))
            else doc.get("due_date", "")
        ),
        "priority": doc.get("priority", 2),
        "completed": bool(doc.get("completed", False)),
        "created_at": (
            doc.get("created_at").isoformat()
            if isinstance(doc.get("created_at"), datetime)
            else None
        ),
        "updated_at": (
            doc.get("updated_at").isoformat()
            if isinstance(doc.get("updated_at"), datetime)
            else None
        ),
    }


with app.app_context():
    col.create_index([("due_date", 1)])
    col.create_index([("created_at", -1)])


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/assignments")
def list_assignments():
    cur = col.find({}).sort([("due_date", 1), ("created_at", -1)])
    return jsonify([serialize(d) for d in cur])


@app.route("/add", methods=["GET", "POST"])
def add_assignment():
    """
    Route for GET and POST requests to the add assignment page.
    GET: Displays a form users can fill out to create a new assignment.
    POST: Accepts the form submission data for a new assignment and saves it to the database.
    Returns:
        GET: rendered template (str): The rendered HTML template.
        POST: redirect (Response): A redirect response to the home page.
    """
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        course = request.form.get("course", "").strip()
        notes = request.form.get("notes", "").strip()
        due_date_str = request.form.get("due_date", "").strip()

        # Handle priority - convert to int or default to 2
        priority_str = request.form.get("priority", "").strip()
        priority = int(priority_str) if priority_str else 2

        if not title or not due_date_str:
            return "Error: Title and due date are required", 400

        try:
            due_date = date.fromisoformat(due_date_str)
            # Convert date to datetime for MongoDB (BSON requires datetime, not date)
            due_datetime = datetime.combine(due_date, datetime.min.time())
        except ValueError:
            return "Error: Invalid due date format", 400

        now = datetime.utcnow()
        doc = {
            "title": title,
            "course": course,
            "notes": notes,
            "due_date": due_datetime,
            "priority": priority,
            "completed": False,
            "created_at": now,
            "updated_at": now,
        }

        col.insert_one(doc)
        return redirect(url_for("index"))

    return render_template("add_assignment.html")


"""
@app.post("/api/assignments")
def create_assignment():
    p = request.get_json(force=True)
    title = (p.get("title") or "").strip()
    due_raw = p.get("due_date")
    course = (p.get("course") or "").strip()
    notes = (p.get("notes") or "").strip()
    if not title or not due_raw:
        return jsonify({"error": "title and due_date required"}), 400
    try:
        due = date.fromisoformat(due_raw)
    except ValueError:
        return jsonify({"error": "invalid due_date"}), 400
    now = datetime.utcnow()
    doc = {
        "title": title,
        "course": course,
        "notes": notes,
        "due_date": due,
        "completed": bool(p.get("completed", False)),
        "created_at": now,
        "updated_at": now,
    }
    _id = col.insert_one(doc).inserted_id
    return jsonify(serialize(col.find_one({"_id": _id}))), 201
"""


@app.patch("/api/assignments/<string:assignment_id>")
def update_assignment(assignment_id):
    try:
        oid = ObjectId(assignment_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    p = request.get_json(force=True)
    update = {}
    if "title" in p:
        update["title"] = (p["title"] or "").strip()
    if "course" in p:
        update["course"] = (p["course"] or "").strip()
    if "notes" in p:
        update["notes"] = (p["notes"] or "").strip()
    if "completed" in p:
        update["completed"] = bool(p["completed"])
    if "due_date" in p:
        try:
            update["due_date"] = date.fromisoformat(p["due_date"])
        except ValueError:
            return jsonify({"error": "invalid due_date"}), 400
    update["updated_at"] = datetime.utcnow()
    col.update_one({"_id": oid}, {"$set": update})
    doc = col.find_one({"_id": oid})
    if not doc:
        return jsonify({"error": "not found"}), 404
    return jsonify(serialize(doc))


@app.delete("/api/assignments/<string:assignment_id>")
def delete_assignment(assignment_id):
    try:
        oid = ObjectId(assignment_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    col.delete_one({"_id": oid})
    return ("", 204)


# Authentication Routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Find user in database
        user = users_col.find_one({"username": username})

        if user and check_password_hash(user["password_hash"], password):
            # Login successful - for now just redirect to home
            flash("Login successful!", "success")
            return redirect("/home")
        else:
            flash("Invalid username or password", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Basic validation
        if not username or not email or not password:
            flash("All fields are required", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("register.html")

        # Check if user already exists
        if users_col.find_one({"username": username}):
            flash("Username already exists", "error")
            return render_template("register.html")

        if users_col.find_one({"email": email}):
            flash("Email already exists", "error")
            return render_template("register.html")

        # Create new user
        password_hash = generate_password_hash(password)
        user_data = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "created_at": datetime.utcnow(),
            "is_active": True,
        }

        users_col.insert_one(user_data)
        flash("Registration successful! Please login.", "success")
        return redirect("/login")

    return render_template("register.html")


@app.route("/home")
def home():
    return render_template("home.html")


@app.route("/logout")
def logout():
    # For now just redirect to home
    flash("Logged out successfully", "success")
    return redirect("/home")


if __name__ == "__main__":
    app.run(debug=True)
