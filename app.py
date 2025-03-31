from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import json
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # Default login page

# File paths
USER_FILE = "users.json"
TOOL_FILE = "tools.json"
LOGS_FILE = "logs.json"


# Ensure JSON files exist
def init_json(file):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)

init_json(USER_FILE)
init_json(TOOL_FILE)
init_json(LOGS_FILE)

# Load and save JSON data
def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# User Model
class User(UserMixin):
    def __init__(self, id, name, password):
        self.id = id
        self.name = name
        self.password = password

# Load Users
@login_manager.user_loader
def load_user(user_id):
    users = load_json(USER_FILE)
    for user in users:
        if user["reg_no"] == user_id:
            return User(user["reg_no"], user["name"], user["password"])
    return None





UPLOAD_FOLDER = './'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No valid file uploaded."})

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file."})

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'attendance.txt')

    try:
        file.save(file_path)
        return jsonify({"status": "success", "message": "File uploaded successfully!", "path": file_path})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to save the file: {str(e)}"})







# Home Page
@app.route("/")
@login_required
def home():
    users = load_json(USER_FILE)
    tools = load_json(TOOL_FILE)
    total_users = len(users)
    total_tools = len(tools)
    
    # Load attendance data safely
    try:
        with open("attendance.txt", "r") as file:
            attendance_data = json.load(file)
            detected_objects = [obj for entry in attendance_data for obj in entry.get("detected_objects", [])]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print("Error loading attendance data:", e)
        detected_objects = []  # Ensure it's always defined
        
    return render_template("index.html", user=current_user, total_users=total_users, total_tools=total_tools, detected_objects=detected_objects)

@app.route("/logs")
@login_required
def logs():
    with open("attendance.txt", "r") as file:
        logs_data = json.load(file)  # Read and parse the JSON data from the logs file
    return render_template("logs.html", logs=logs_data)



# Login Page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        reg_no = request.form["reg_no"]
        password = request.form["password"]
        users = load_json(USER_FILE)

        for user in users:
            if user["reg_no"] == reg_no and user["password"] == password:
                login_user(User(user["reg_no"], user["name"], user["password"]))
                return redirect(url_for("home"))

    return render_template("login.html", error="Invalid credentials!" if request.method == "POST" else None)

# Logout Route
@app.route("/logout")
@login_required  # Protect logout route to ensure only logged-in users can log out
def logout():
    logout_user()
    return redirect(url_for("login"))

# Manage Users
@app.route("/users", methods=["GET", "POST"])
@login_required  # Protect this route to ensure only logged-in users can access it
def users_page():
    users = load_json(USER_FILE)

    if request.method == "POST":
        name = request.form.get("name").strip()
        reg_no = request.form.get("reg_no").strip()

        if name and reg_no:
            if not any(user["reg_no"] == reg_no for user in users):  # Prevent duplicates
                users.append({"name": name, "reg_no": reg_no})
                save_json(USER_FILE, users)
        return redirect(url_for("users_page"))

    return render_template("users.html", users=users)

# Edit User
@app.route("/edit_user/<reg_no>", methods=["POST"])
@login_required
def edit_user(reg_no):
    users = load_json(USER_FILE)
    for user in users:
        if user["reg_no"] == reg_no:
            user["name"] = request.form.get("name").strip()
            save_json(USER_FILE, users)
            break
    return redirect(url_for("users_page"))

# Delete User
@app.route("/delete_user/<reg_no>")
@login_required
def delete_user(reg_no):
    users = load_json(USER_FILE)
    users = [user for user in users if user["reg_no"] != reg_no]
    save_json(USER_FILE, users)
    return redirect(url_for("users_page"))

# Manage Tools
@app.route("/tools", methods=["GET", "POST"])
@login_required  # Protect this route to ensure only logged-in users can access it
def tools_page():
    tools = load_json(TOOL_FILE)

    if request.method == "POST":
        name = request.form.get("name").strip()
        tool_id = request.form.get("id").strip()

        if name and tool_id:
            if not any(tool["id"] == tool_id for tool in tools):  # Prevent duplicates
                tools.append({"name": name, "id": tool_id})
                save_json(TOOL_FILE, tools)
        return redirect(url_for("tools_page"))

    return render_template("tools.html", tools=tools)

# Edit Tool
@app.route("/edit_tool/<tool_id>", methods=["POST"])
@login_required
def edit_tool(tool_id):
    tools = load_json(TOOL_FILE)
    for tool in tools:
        if tool["id"] == tool_id:
            tool["name"] = request.form.get("name").strip()
            save_json(TOOL_FILE, tools)
            break
    return redirect(url_for("tools_page"))

# Delete Tool
@app.route("/delete_tool/<tool_id>")
@login_required
def delete_tool(tool_id):
    tools = load_json(TOOL_FILE)
    tools = [tool for tool in tools if tool["id"] != tool_id]
    save_json(TOOL_FILE, tools)
    return redirect(url_for("tools_page"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
