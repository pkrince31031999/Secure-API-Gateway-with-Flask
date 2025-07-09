from flask import Flask,request, jsonify
from db import get_db_connection
from dotenv import load_dotenv
import os
from tasks import process_csv
from werkzeug.utils import secure_filename


load_dotenv()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app = Flask(__name__)

@app.route("/profile", methods=["POST","GET"])
def profile():
    conn = get_db_connection()
    data = request.args
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error","status_code": 400,"message": "User ID is required"}), 400
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, first_name, middle_name, last_name, email, phone_number, role, profile_pic_path FROM users WHERE id = %s", (user_id))
        user = cursor.fetchone()
        if not user:
            return jsonify({"status": "error","status_code": 404,"message": "User not found"}), 404
        return jsonify({"status": "success","status_code": 200,"data": user}), 200
    
@app.route("/profiles", methods=["GET"])
def profiles():
    conn = get_db_connection()
    page_size = int(request.args.get("page_size", 10))
    current_page = int(request.args.get("page", 1))
    offset = (current_page - 1) * page_size
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, first_name, middle_name, last_name, email, phone_number, role, profile_pic_path FROM users ORDER BY id DESC limit %s offset %s", (page_size, offset))
        users = cursor.fetchall()
        return jsonify({"status": "success","status_code": 200,"data": users}), 200 
   
@app.route("/profileUpdate", methods=["POST"])
def profileUpdate():
    conn         = get_db_connection()
    data         = request.get_json()  
    user_id      = data.get("user_id")
    first_name   = data.get("first_name")
    middle_name  = data.get("middle_name")
    last_name    = data.get("last_name")
    email        = data.get("email")
    phone_number = data.get("phone_number")
    profile_pic  = data.get("profile_pic")

    if not first_name or not last_name:
        return jsonify({"status": "error","status_code": 400,"message": "First name and last name are required"}), 400
    if not email:
        return jsonify({"status": "error","status_code": 400,"message": "Email is required"}), 400
    if not phone_number or len(phone_number) != 10:
        return jsonify({"status": "error","status_code": 400,"message": "Please enter valid phone number"}), 400
    if not user_id:
        return jsonify({"status": "error","status_code": 400,"message": "User ID is required"}), 400
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id))
        user = cursor.fetchone()
        if user and user.get("role") == "user":
            return jsonify({"status": "error","status_code": 400,"message": "You are not authorized to update user data."}), 400   
        else:
            if not user:
                return jsonify({"status": "error","status_code": 404,"message": "User not found"}), 404
            
    with conn.cursor() as cursor:
        cursor.execute("Update users SET first_name=%s, middle_name=%s, last_name=%s, email=%s, phone_number=%s, profile_pic_path=%s WHERE id = %s", (first_name, middle_name, last_name, email, phone_number, profile_pic, user_id))
        cursor.connection.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error","status_code": 404,"message": "User not Updated Successfully"}), 404
        return jsonify({"status": "success","status_code": 200,"message": "User Data Updated Successfully"}), 200

@app.route("/profileDelete", methods=["DELETE"])
def profileDelete():
    conn = get_db_connection()
    data = request.args
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error","status_code": 400,"message": "User ID is required"}), 400
    
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id))
        cursor.connection.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error","status_code": 404,"message": "User not Deleted Successfully"}), 404
        return jsonify({"status": "success","status_code": 200,"message": "User Deleted Successfully"}), 200

@app.route("/profileBulkUpload", methods=["POST"])
def profile_bulk_upload():
    uploaded_file = request.files.get('uploaded_file')
    
    if not uploaded_file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = secure_filename(uploaded_file.filename)
    
    if filename.endswith('.csv') or filename.endswith('.xlsx'):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        uploaded_file.save(filepath)
        
        # Trigger background job
        process_csv.delay(filepath)

        return jsonify({"message": "File uploaded. Processing started."}), 202

    return jsonify({"error": "Invalid file format"}), 400

        
if __name__ == "__main__":
    app.run(port=5001)
