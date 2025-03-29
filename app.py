from flask import Flask, render_template, request, redirect, url_for, jsonify, session, Response
import json
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import cv2
import numpy as np
import face_recognition
import requests
from datetime import datetime

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









# Load Haar cascade for face detection
haarcascade_path = 'haarcascade_frontalface_default.xml'
if not os.path.exists(haarcascade_path):
    print("Error: Haar cascade file not found!")
    exit()

face_classifier = cv2.CascadeClassifier(haarcascade_path)

# Path to the database of known faces
database_path = 'database/'
faces_dict = {}

# Attendance file
attendance_file = "attendance.txt"

# Load known faces from the database
print("Loading face encodings...")

for person_name in os.listdir(database_path):
    person_folder = os.path.join(database_path, person_name)

    if os.path.isdir(person_folder):
        encodings = []

        for filename in os.listdir(person_folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
                file_path = os.path.join(person_folder, filename)
                try:
                    face_img = face_recognition.load_image_file(file_path)
                    face_enc = face_recognition.face_encodings(face_img)

                    if face_enc:
                        encodings.append(face_enc[0])
                        print(f"✔ Face encoded for {person_name} from {filename}")
                    else:
                        print(f"❌ No face found in {filename}")

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

        if encodings:
            faces_dict[person_name] = encodings
        else:
            print(f"⚠ Warning: No valid face encodings found for {person_name}")

print("Face encoding loading complete.\n")

# Function to send attendance to the server
def send_attendance():
    url = "https://voting.softechsupply.com/dashboard/ai_data.php"
    
    if not os.path.exists(attendance_file):
        print("Error: Attendance file not found!")
        return
    
    try:
        with open(attendance_file, "rb") as file:
            files = {"file": file}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            print("✔ Attendance file successfully sent to server.")
        else:
            print(f"❌ Failed to send file. Server response: {response.status_code}")

    except Exception as e:
        print(f"Error sending attendance file: {e}")

# Load object detection model
net_file = 'MobileNetSSD/deploy.prototxt'
caffe_model = 'MobileNetSSD/mobilenet_iter_73000.caffemodel'
if not os.path.exists(net_file) or not os.path.exists(caffe_model):
    print("Error: Object detection model files not found!")
    exit()

net = cv2.dnn.readNetFromCaffe(net_file, caffe_model)

# Load class labels for object detection
class_labels = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car",
    "cat", "chair", "cow", "dining table", "dog", "horse", "motorbike", "person",
    "potted plant", "sheep", "sofa", "train", "tv monitor", "motorcycle",
    "airplane", "truck", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "couch", "bed", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster",
    "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush"
]

# Function to save attendance without duplicating entries for the same date
def save_attendance(name, detected_objects=None):
    try:
        # Load existing attendance records
        if os.path.exists(attendance_file) and os.path.getsize(attendance_file) > 0:
            with open(attendance_file, "r") as file:
                try:
                    attendance_data = json.load(file)
                except json.JSONDecodeError:
                    attendance_data = []
        else:
            attendance_data = []

        # Get the current date
        today_date = datetime.now().strftime("%Y-%m-%d")

        # Check if the user is already recorded for today
        existing_entry = None
        for entry in attendance_data:
            if entry["name"] == name and entry["datetime"].startswith(today_date):
                existing_entry = entry
                break

        if existing_entry:
            # Remove the existing entry for that person on this date
            attendance_data.remove(existing_entry)
            print(f"⚠ {name} already marked present today. Replacing old entry.")

        # Append new record
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        attendance_record = {"name": name, "datetime": now}

        if detected_objects:
            attendance_record["detected_objects"] = detected_objects

        attendance_data.append(attendance_record)

        # Save back to file
        with open(attendance_file, "w") as file:
            json.dump(attendance_data, file, indent=4)

        print(f"✔ Attendance recorded for {name} at {now}")

    except Exception as e:
        print(f"Error saving attendance: {e}")

# Flask route for streaming video feed
@app.route('/video_feed')
def video_feed():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Function to generate video frames for the video stream
# Function to generate video frames for the video stream
def generate():
    cap = cv2.VideoCapture(0)
    recognized_people = set()  # To avoid duplicate entries

    if not cap.isOpened():
        print("Error: Unable to access the webcam.")
        exit()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Unable to read from the webcam.")
            break

        # Object Detection
        # Convert the frame to a blob for object detection
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), (127.5, 127.5, 127.5), swapRB=False)
        net.setInput(blob)
        detections = net.forward()

        # Process detected objects
        height, width = frame.shape[:2]
        detected_objects = []

        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]

            if confidence > 0.2:  # You can adjust the confidence threshold
                idx = int(detections[0, 0, i, 1])
                label = class_labels[idx]
                if label != "background":  # Don't display the background class
                    detected_objects.append(label)

                    box = detections[0, 0, i, 3:7] * np.array([width, height, width, height])
                    (x, y, x2, y2) = box.astype("int")

                    # Draw bounding box and label
                    cv2.rectangle(frame, (x, y), (x2, y2), (0, 255, 0), 2)
                    label_text = f"{label}: {confidence:.2f}"
                    cv2.putText(frame, label_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Convert the frame to grayscale for face detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_classifier.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

        # Process detected faces
        for (x, y, w, h) in faces:
            face = frame[y:y+h, x:x+w]
            face_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)

            try:
                face_encodings = face_recognition.face_encodings(face_rgb)

                if not face_encodings:
                    continue

                unknown_encoding = face_encodings[0]
                best_match = None

                for name, encodings in faces_dict.items():
                    matches = face_recognition.compare_faces(encodings, unknown_encoding, tolerance=0.5)
                    if any(matches):
                        best_match = name
                        break

                if best_match:
                    print(f"✔ Recognized: {best_match}")
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    text_size = cv2.getTextSize(best_match, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
                    cv2.rectangle(frame, (x, y - text_size[1] - 10), (x + text_size[0], y), (0, 0, 0), -1)
                    cv2.putText(frame, best_match, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                    # Save attendance only if the person is recognized for the first time and not recorded today
                    if best_match not in recognized_people:
                        recognized_people.add(best_match)
                        save_attendance(best_match, detected_objects)
                        send_attendance()

            except Exception as e:
                print(f"Error in face recognition: {e}")

        # Show the result frame
        ret, jpeg = cv2.imencode('.jpg', frame)
        if ret:
            frame = jpeg.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')






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

# Home Page
@app.route("/")
@login_required
def home():
    users = load_json(USER_FILE)
    tools = load_json(TOOL_FILE)
    total_users = len(users)
    total_tools = len(tools)
    return render_template("index.html", user=current_user, total_users=total_users, total_tools=total_tools)

@app.route("/logs")
@login_required
def logs():
    with open("logs.txt", "r") as file:
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
