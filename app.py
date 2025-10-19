import os
import csv
from io import StringIO
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, Response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId
from collections import defaultdict
from pydantic import ValidationError

from models import (
    AssignmentCreate,
    AssignmentUpdate,
    assignment_to_dict,
    assignment_update_to_dict,
    serialize_assignment
)

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

client = MongoClient(
    os.getenv("MONGO_URI"),
    username=os.getenv("MONGO_USER"),
    password=os.getenv("MONGO_PASS"),
)
db = client["homeworkdb"]
col = db["assignments"]
users_col = db["users"]

class User(UserMixin):
    def __init__(self, user_id, username, email):
        self.id = user_id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    """Load user from database for Flask-Login"""
    user_doc = users_col.find_one({"_id": ObjectId(user_id)})
    if user_doc:
        return User(
            user_id=str(user_doc["_id"]),
            username=user_doc["username"],
            email=user_doc["email"]
        )
    return None

def group_by_date(assignments):
    """Group assignments by due date with formatted labels"""
    groups = defaultdict(list)
    for a in assignments:
        due = a.get('due_date')
        try:
            # Handle datetime objects
            if isinstance(due, datetime):
                label = due.strftime("%a, %b %d")
            # Handle date objects
            elif isinstance(due, date):
                label = due.strftime("%a, %b %d")
            # Handle string dates (from serialization)
            elif isinstance(due, str):
                due_date = datetime.strptime(due, "%Y-%m-%d")
                label = due_date.strftime("%a, %b %d")
            else:
                label = "Unknown"
        except (ValueError, AttributeError):
            label = "Unknown"
        groups[label].append(a)
    return groups

def calculate_assignment_status(assignment):
    """
    Calculate status flags for an assignment.
    
    Args:
        assignment: Assignment dictionary with due_date and completed fields
    
    Returns:
        Dictionary with 'is_overdue' and 'is_due_soon' boolean flags
    """
    status = {
        'is_overdue': False,
        'is_due_soon': False
    }
    
    if assignment.get('completed', False):
        return status
    
    due = assignment.get('due_date')
    if not due:
        return status
    
    # Convert due_date to datetime for comparison
    try:
        if isinstance(due, str):
            due_datetime = datetime.strptime(due, "%Y-%m-%d")
        elif isinstance(due, date) and not isinstance(due, datetime):
            due_datetime = datetime.combine(due, datetime.min.time())
        elif isinstance(due, datetime):
            due_datetime = due
        else:
            return status
        
        now = datetime.now()
        # Normalize to midnight for comparison
        now_midnight = datetime.combine(now.date(), datetime.min.time())
        due_midnight = datetime.combine(due_datetime.date(), datetime.min.time())
        
        if due_midnight < now_midnight:
            status['is_overdue'] = True
        
        # If due date is within 24 hours, the assignment is "due soon"
        time_until_due = due_datetime - now
        if timedelta(0) <= time_until_due <= timedelta(hours=24):
            status['is_due_soon'] = True
            
    except (ValueError, AttributeError, TypeError):
        pass
    
    return status


with app.app_context():
    col.create_index([("due_date", 1)])
    col.create_index([("created_at", -1)])
    col.create_index([("course", 1)])
    col.create_index([("updated_at", -1)])
    col.create_index([("completed", 1), ("updated_at", -1)])
    col.create_index([("user_id", 1)])

@app.get("/")
def index():
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    
    # Exclude assignments which were marked "complete" more than 24 hours ago
    query = {
        "$or": [
            {"completed": {"$ne": True}},
            {"completed": True, "updated_at": {"$gte": twenty_four_hours_ago}}
        ]
    }
    
    cursor = col.find(query).sort([("due_date", 1), ("created_at", -1)])
    assignments = [serialize_assignment(doc) for doc in cursor]
    
    for assignment in assignments:
        status = calculate_assignment_status(assignment)
        assignment.update(status)
    
    grouped_assignments = group_by_date(assignments)
    
    if current_user.is_authenticated:
        return render_template("index.html", grouped_assignments=grouped_assignments, has_assignments=len(assignments) > 0)
    return redirect(url_for("login"))

@app.route("/add", methods=["GET", "POST"])
@login_required
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
        try:
            # If priority is not provided, default to 2
            priority_str = request.form.get("priority", "").strip()
            priority = int(priority_str) if priority_str else 2
            
            estimated_time_str = request.form.get("estimated_time", "").strip()
            estimated_time = int(estimated_time_str) if estimated_time_str else None
            
            assignment_data = AssignmentCreate(
                user_id: current_user.id,
                title=request.form.get("title", ""),
                course=request.form.get("course", ""),
                notes=request.form.get("notes", ""),
                due_date=date.fromisoformat(request.form.get("due_date", "")),
                priority=priority,
                estimated_time=estimated_time,
                completed=False
            )
            
            doc = assignment_to_dict(assignment_data)
            col.insert_one(doc)
            
            flash("Assignment created successfully!", "success")
            return redirect(url_for("index"))
            
        except ValueError as e:
            flash(f"Error: Invalid date format - {str(e)}", "error")
            return render_template("add_assignment.html"), 400
        except ValidationError as e:
            errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
            flash(f"Validation error: {errors}", "error")
            return render_template("add_assignment.html"), 400
    
    return render_template("add_assignment.html")

@app.post("/toggle/<string:assignment_id>")
@login_required
def toggle_assignment(assignment_id):
    """Toggle the completed status of an assignment"""
    try:
        oid = ObjectId(assignment_id)
    except Exception:
        return "Invalid assignment ID", 400
    
    doc = col.find_one({"_id": oid})
    if not doc:
        return "Assignment not found", 404
    
    new_completed = not bool(doc.get("completed", False))
    col.update_one(
        {"_id": oid},
        {"$set": {"completed": new_completed, "updated_at": datetime.utcnow()}},
        {"user_id": current_user.id}
    )
    
    return redirect(url_for("index"))

@app.post("/delete/<string:assignment_id>")
@login_required
def delete_assignment(assignment_id):
    """Delete an assignment"""
    try:
        oid = ObjectId(assignment_id)
    except Exception:
        return "Invalid assignment ID", 400
    
    col.delete_one({"_id": oid, "user_id": current_user.id})
    return redirect(url_for("index"))

@app.route("/edit/<string:assignment_id>", methods=["GET", "POST"])
@login_required
def edit_assignment(assignment_id):
    """Edit an existing assignment"""
    try:
        oid = ObjectId(assignment_id)
    except Exception:
        flash("Invalid assignment ID", "error")
        return redirect(url_for("index"))
    
    doc = col.find_one({"_id": oid})
    if not doc:
        flash("Assignment not found", "error")
        return redirect(url_for("index"))
    
    if request.method == "POST":
        try:
            # If priority is not provided, default to 2
            priority_str = request.form.get("priority", "").strip()
            priority = int(priority_str) if priority_str else 2
            
            estimated_time_str = request.form.get("estimated_time", "").strip()
            estimated_time = int(estimated_time_str) if estimated_time_str else None
            
            assignment_data = AssignmentUpdate(
                user_id=current_user.id,
                title=request.form.get("title", ""),
                course=request.form.get("course", ""),
                notes=request.form.get("notes", ""),
                due_date=date.fromisoformat(request.form.get("due_date", "")),
                priority=priority,
                estimated_time=estimated_time
            )
            
            update_doc = assignment_update_to_dict(assignment_data)
            col.update_one({"_id": oid, "user_id": current_user.id}, {"$set": update})
            
            flash("Assignment updated successfully!", "success")
            return redirect(url_for("index"))
            
        except ValueError as e:
            flash(f"Error: Invalid date format - {str(e)}", "error")
            assignment = serialize_assignment(doc)
            return render_template("edit_assignment.html", assignment=assignment), 400
        except ValidationError as e:
            errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
            flash(f"Validation error: {errors}", "error")
            assignment = serialize_assignment(doc)
            return render_template("edit_assignment.html", assignment=assignment), 400
    
    # GET request: show edit form
    assignment = serialize_assignment(doc)
    return render_template("edit_assignment.html", assignment=assignment)

@app.route("/search")
@login_required
def search():
    """Search and filter assignments"""
    text_query = request.args.get("q", "").strip()
    course_filter = request.args.get("course", "").strip()
    due_start = request.args.get("due_start", "").strip()
    due_end = request.args.get("due_end", "").strip()
    time_min = request.args.get("time_min", "").strip()
    time_max = request.args.get("time_max", "").strip()
    show_completed = request.args.get("show_completed", "").lower() == "true"
    
    query = {"user_id": current_user.id}
    
    # Text search on title and notes
    if text_query:
        query["$or"] = [
            {"title": {"$regex": text_query, "$options": "i"}},
            {"notes": {"$regex": text_query, "$options": "i"}}
        ]
    
    # Course filter
    if course_filter:
        query["course"] = course_filter
    
    # Due date range filter
    if due_start or due_end:
        date_query = {}
        if due_start:
            try:
                start_datetime = datetime.combine(
                    date.fromisoformat(due_start),
                    datetime.min.time()
                )
                date_query["$gte"] = start_datetime
            except ValueError:
                pass
        if due_end:
            try:
                end_datetime = datetime.combine(
                    date.fromisoformat(due_end),
                    datetime.max.time()
                )
                date_query["$lte"] = end_datetime
            except ValueError:
                pass
        if date_query:
            query["due_date"] = date_query
    
    # Estimated time filter
    if time_min or time_max:
        time_query = {}
        if time_min:
            try:
                time_query["$gte"] = int(time_min)
            except ValueError:
                pass
        if time_max:
            try:
                time_query["$lte"] = int(time_max)
            except ValueError:
                pass
        if time_query:
            query["estimated_time"] = time_query
    
    # If show_completed is True, show all assignments. If false, show only uncompleted assignments
    if not show_completed:
        query["completed"] = {"$ne": True}
    
    # Limit to 100 results for performance
    cursor = col.find(query).sort([("due_date", 1), ("created_at", -1)]).limit(100)
    assignments = [serialize_assignment(doc) for doc in cursor]
    
    for assignment in assignments:
        status = calculate_assignment_status(assignment)
        assignment.update(status)
    
    all_courses = col.distinct("course", {"course": {"$ne": ""}})
    
    filters = {
        "q": text_query,
        "course": course_filter,
        "due_start": due_start,
        "due_end": due_end,
        "time_min": time_min,
        "time_max": time_max,
        "show_completed": show_completed
    }
    
    return render_template(
        "search.html",
        assignments=assignments,
        all_courses=sorted(all_courses),
        filters=filters,
        has_results=len(assignments) > 0
    )

@app.route("/export")
@login_required
def export_assignments():
    """Export filtered assignments as CSV"""
    text_query = request.args.get("q", "").strip()
    course_filter = request.args.get("course", "").strip()
    due_start = request.args.get("due_start", "").strip()
    due_end = request.args.get("due_end", "").strip()
    time_min = request.args.get("time_min", "").strip()
    time_max = request.args.get("time_max", "").strip()
    show_completed = request.args.get("show_completed", "").lower() == "true"
    
    query = {"user_id": current_user.id}
    
    if text_query:
        query["$or"] = [
            {"title": {"$regex": text_query, "$options": "i"}},
            {"notes": {"$regex": text_query, "$options": "i"}}
        ]
    
    if course_filter:
        query["course"] = course_filter
    
    if due_start or due_end:
        date_query = {}
        if due_start:
            try:
                start_datetime = datetime.combine(
                    date.fromisoformat(due_start),
                    datetime.min.time()
                )
                date_query["$gte"] = start_datetime
            except ValueError:
                pass
        if due_end:
            try:
                end_datetime = datetime.combine(
                    date.fromisoformat(due_end),
                    datetime.max.time()
                )
                date_query["$lte"] = end_datetime
            except ValueError:
                pass
        if date_query:
            query["due_date"] = date_query
    
    if time_min or time_max:
        time_query = {}
        if time_min:
            try:
                time_query["$gte"] = int(time_min)
            except ValueError:
                pass
        if time_max:
            try:
                time_query["$lte"] = int(time_max)
            except ValueError:
                pass
        if time_query:
            query["estimated_time"] = time_query
    
    # If show_completed is True, show all assignments. If false, show only uncompleted assignments
    if not show_completed:
        query["completed"] = {"$ne": True}
    
    cursor = col.find(query).sort([("due_date", 1), ("created_at", -1)])
    assignments = [serialize_assignment(doc) for doc in cursor]
    
    # Generate CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["Title", "Course", "Due Date", "Priority", "Estimated Time (min)", "Notes", "Completed"])
    
    # Data
    for assignment in assignments:
        writer.writerow([
            assignment.get("title", ""),
            assignment.get("course", ""),
            assignment.get("due_date", ""),
            assignment.get("priority", ""),
            assignment.get("estimated_time", "") or "",
            assignment.get("notes", ""),
            "Yes" if assignment.get("completed", False) else "No"
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=assignments.csv"}
    )

# Authentication Routes
@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Find user in database
        user_doc = users_col.find_one({"username": username})

        if user_doc and check_password_hash(user_doc["password_hash"], password):
            # Create User object and login with Flask-Login
            user = User(
                user_id=str(user_doc["_id"]),
                username=user_doc["username"],
                email=user_doc["email"]
            )
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("index"))
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
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
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
    """Home page - redirect to index if authenticated"""
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("home.html")


@app.route("/logout")
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 10000)))
