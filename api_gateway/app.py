from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
import os
import requests
import boto3
from db import get_db_connection
import hashlib
from werkzeug.utils import secure_filename
import uuid
from tasks import process_csv

load_dotenv()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
jwt = JWTManager(app)
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)


@app.route("/create_user", methods=["POST"])
def create_customer():
    
    """
    Create a new user.

    Request Body:
        - first_name (string): First name of the user.
        - middle_name (string): Middle name of the user.
        - last_name (string): Last name of the user.
        - email (string): Email of the user.
        - phone_number (string): Phone number of the user.
        - password (string): Password of the user.
        - role (string): Role of the user (Sub-admin, admin, user).
        - profile_pic (file): Profile picture of the user.

    Returns:
        - status (string): success or error
        - status_code (int): HTTP status code
        - message (string): Success message or error message
    """
    conn = get_db_connection()
    first_name  = request.form.get("first_name")
    middle_name = request.form.get("middle_name")
    last_name   = request.form.get("last_name")
    email       = request.form.get("email")
    phone_number= request.form.get("phone_number")
    password    = request.form.get("password")
    profile_pic = request.files.get("profile_pic")
    role        = request.form.get("role")
    makeHashpassword = hashlib.md5(password.encode('utf-8')).hexdigest()
    roleList = ["Sub-admin","admin", "user"]
     

    if not first_name or not last_name:
        return jsonify({"message": "First name and last name are required"}), 400
    
    if not email:
        return jsonify({"message": "Email is required"}), 400
    
    if not phone_number or len(phone_number) != 10:
        return jsonify({"message": "Please enter valid phone number"}), 400
    
    if not password:
        return jsonify({"message": "Password is required"}), 400
    
    if role not in roleList:
        return jsonify({"message": "Please enter valid role i.e Sub-admin, admin, user"}), 400
    
    if profile_pic:
        filename = secure_filename(profile_pic.filename)
        unique_filename = f"profile_pics/{uuid.uuid4().hex}_{filename}"

        # Upload to S3
        s3_client.upload_fileobj(
            profile_pic,
            S3_BUCKET,
            unique_filename,
            ExtraArgs={
                "ContentType": profile_pic.content_type
            }
        )

        file_pic = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{unique_filename}"

    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE email = %s OR phone_number = %s", (email, phone_number))
        if cursor.fetchone():
            return jsonify({ "status": "error","message": "Email or phone number already in use", "status_code": 400}), 400
    
    conn.cursor().execute(f"INSERT INTO users (first_name, middle_name, last_name, email, profile_pic_path, phone_number, password, role) VALUES ('{first_name}', '{middle_name}', '{last_name}', '{email}', '{unique_filename}', '{phone_number}', '{makeHashpassword}', '{role}')")
    conn.commit()
    conn.close()

    return jsonify({"status": "success","status_code": 200,"message": "User created successfully"}), 201

@app.route("/login", methods=["POST"])
def login():
    """
    Login API
    
    Parameters:
        - email (string): email address of user
        - password (string): password of user
    
    Returns:
        - access_token (string): JWT access token
        - msg (string): Success message or error message
    """
    conn = get_db_connection()
    email = request.json.get("email")
    password = request.json.get("password")
    if not email:
        return jsonify(msg="Email ID is required"), 400
    
    if not password:
        return jsonify(msg="Password is required"), 400
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email))
        user = cursor.fetchone()
        if not user:
            return jsonify(msg="Invalid User Credentials!"), 401
        
    if email == user["email"] and hashlib.md5(password.encode('utf-8')).hexdigest() == user["password"]:
        token = create_access_token(identity=email)
        return jsonify(access_token=token), 200
    return jsonify(msg="Invalid credentials"), 401

@app.route("/user", methods=["GET"])
@jwt_required()
def proxy_user_service():
    """
    Proxy the user profile API to the user service.

    Parameters:
        - user_id (string): ID of the user to fetch the profile of

    Returns:
        - status (string): success or error
        - status_code (int): HTTP status code
        - message (string): Success message or error message
        - data (dict): User profile data
    """
    user_id = request.args.get("user_id")
    headers = {"Authorization": request.headers["Authorization"]}
    resp = requests.get(os.getenv("USER_SERVICE_URL") + f"/profile?user_id={user_id}", headers=headers)
    return jsonify(resp.json()), resp.status_code

@app.route("/users", methods=["GET"])
@jwt_required()
def proxy_users_services():
    """
    Proxy the user profiles API to the user service.

    Parameters:
        - page_size (string): Number of profiles per page
        - current_page (string): Current page number

    Returns:
        - status (string): success or error
        - status_code (int): HTTP status code
        - data (list): List of user profiles
    """

    page_size = request.args.get("page_size")
    current_page = request.args.get("page")
    headers = {"Authorization": request.headers["Authorization"]}
    resp = requests.get(os.getenv("USER_SERVICE_URL") + f"/profiles?page_size={page_size}&page={current_page}", headers=headers)
    return jsonify(resp.json()), resp.status_code

@app.route("/user-update", methods=["POST"])
@jwt_required()
def proxy_user_update_service():
    """
    Proxy the user update API to the user service.

    Parameters:
        - first_name (string): First name of the user
        - middle_name (string): Middle name of the user
        - last_name (string): Last name of the user
        - email (string): Email of the user
        - phone_number (string): Phone number of the user
        - profile_pic (file): Profile picture of the user

    Returns:
        - status (string): success or error
        - status_code (int): HTTP status code
        - message (string): Success message or error message
    """
    data = request.json
    resp = requests.post(
                os.getenv("USER_SERVICE_URL") + "/profileUpdate",
                headers={"Content-Type": "application/json", "Authorization": request.headers["Authorization"]},
                json=data 
            )
    return jsonify(resp.json()), resp.status_code

@app.route("/delete-user", methods=["DELETE"])
@jwt_required()
def proxy_delete_user_service():
    """
    Proxy the user delete API to the user service.

    Parameters:
        - user_id (string): ID of the user to delete

    Returns:
        - status (string): success or error
        - status_code (int): HTTP status code
        - message (string): Success message or error message
    """
    user_id = request.args.get("user_id")
    headers = {"Authorization": request.headers["Authorization"]}
    resp = requests.delete(os.getenv("USER_SERVICE_URL") + f"/profileDelete?user_id={user_id}", headers=headers)
    return jsonify(resp.json()), resp.status_code

@app.route("/data", methods=["GET"])
@jwt_required()
def proxy_data_service():
    headers = {"Authorization": request.headers["Authorization"]}
    resp = requests.get(os.getenv("DATA_SERVICE_URL") + "/info", headers=headers)
    return jsonify(resp.json()), resp.status_code

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_csv():
    uploaded_file = request.files.get('uploaded_file')

    if not uploaded_file:
        return jsonify({"error": "No file uploaded"}), 400
    
    resp = requests.post(
        os.getenv("USER_SERVICE_URL") + "/profileBulkUpload",
        headers={"Authorization": request.headers["Authorization"]},
        files={
            'uploaded_file': (
                uploaded_file.filename,
                uploaded_file.stream,
                uploaded_file.content_type
            )
        }
    )

    return jsonify(resp.json()), resp.status_code

   
if __name__ == "__main__":
    app.run(port=5000, debug=True)
