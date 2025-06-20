import psycopg2
import psycopg2.extras
import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt

app = Flask(__name__)
CORS(app)

# Database connection details (ensure these are correct)
DB_HOST = "dpg-d1aovm6uk2gs7390cttg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_um2n"
DB_USER = "shadowfly_um2n_user"
DB_PASS = "6ab9pofT8Tv0H5TqLWiD0qJZ0fTR8aNk"
DB_PORT = 5432

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_connection():
    """Establishes and returns a database connection."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        logging.info("Database connection successful")
    except psycopg2.Error as e:
        logging.error(f"Error connecting to database: {e}")
        raise
    return conn



def create_tables():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users_data (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255), -- Increased length for hashed passwords
                role VARCHAR(50) NOT NULL,
                phone_number VARCHAR(225),
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
 
        
        app.logger.info("Table 'users_data' ensured to exist.")

        conn.commit()
    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"Error creating tables: {e}")
        if conn: conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()

# --- Rest of your Flask application code ---

create_tables() 

@app.route('/')
def home():
    return "Flask backend is running!"

@app.route('/add_user', methods=['POST'])
def add_user():
    """Endpoint to add a new user to the users_data table."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required_fields = ['full_name', 'email', 'username', 'role', 'phone_number', 'status']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    full_name = data.get('full_name')
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    # Hash the password if provided, otherwise set to None
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') if password else None
    role = data.get('role')
    phone_number = data.get('phone_number')
    status = data.get('status')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        insert_query = """
        INSERT INTO users_data (full_name, email, username, password, role, phone_number, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """
        cur.execute(insert_query, (full_name, email, username, hashed_password, role, phone_number, status))
        new_user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        logging.info(f"User '{username}' added successfully with ID: {new_user_id}")
        return jsonify({"message": "User added successfully", "id": new_user_id}), 201

    except psycopg2.errors.UniqueViolation as e:
        conn.rollback()
        logging.error(f"Duplicate entry error: {e}")
        return jsonify({"error": "A user with this email or username already exists."}), 409
    except psycopg2.Error as e:
        conn.rollback()
        logging.error(f"Database error during user insertion: {e}")
        return jsonify({"error": "Failed to add user due to a database error."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Endpoint to update an existing user in the users_data table."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    full_name = data.get('full_name')
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') if password else None
    role = data.get('role')
    phone_number = data.get('phone_number')
    status = data.get('status')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        update_query = """
        UPDATE users_data
        SET full_name = %s, email = %s, username = %s, password = %s, role = %s,
            phone_number = %s, status = %s
        WHERE id = %s;
        """
        cur.execute(update_query, (full_name, email, username, hashed_password, role, phone_number, status, user_id))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({"error": "User not found."}), 404

        cur.close()
        logging.info(f"User with ID: {user_id} updated successfully.")
        return jsonify({"message": "User updated successfully"}), 200

    except psycopg2.errors.UniqueViolation as e:
        conn.rollback()
        logging.error(f"Duplicate entry error: {e}")
        return jsonify({"error": "A user with this email or username already exists."}), 409
    except psycopg2.Error as e:
        conn.rollback()
        logging.error(f"Database error during user update: {e}")
        return jsonify({"error": "Failed to update user due to a database error."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Endpoint to delete a user from the users_data table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        delete_query = "DELETE FROM users_data WHERE id = %s;"
        cur.execute(delete_query, (user_id,))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({"error": "User not found."}), 404

        cur.close()
        logging.info(f"User with ID: {user_id} deleted successfully.")
        return jsonify({"message": "User deleted successfully"}), 200

    except psycopg2.Error as e:
        conn.rollback()
        logging.error(f"Database error during user deletion: {e}")
        return jsonify({"error": "Failed to delete user due to a database error."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during user deletion: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/get_users', methods=['GET'])
def get_users():
    """Endpoint to retrieve all users from the users_data table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, full_name, email, username, role, phone_number, status FROM users_data ORDER BY id DESC;")
        users = cur.fetchall()
        cur.close()
        users_list = [dict(user) for user in users]
        logging.info(f"Fetched {len(users_list)} users.")
        return jsonify(users_list), 200
    except psycopg2.Error as e:
        logging.error(f"Database error during user retrieval: {e}")
        return jsonify({"error": "Failed to retrieve users due to a database error."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during user retrieval: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/login', methods=['POST'])
def login():
    """Endpoint for user login."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # Select username, password, and full_name for login verification
        cur.execute("SELECT username, password, full_name FROM users_data WHERE username = %s;", (username,))
        user = cur.fetchone()
        cur.close()

        if user:
            stored_password = user['password']
            full_name = user['full_name'] # Get full_name
            if stored_password:
                # If password is set (not null), compare with hashed password
                if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                    logging.info(f"User '{username}' logged in successfully.")
                    return jsonify({"message": "Login successful", "full_name": full_name, "username": username}), 200 # Return full_name and username
                else:
                    logging.warning(f"Failed login attempt for user '{username}': Invalid password.")
                    return jsonify({"error": "Invalid username or password"}), 401
            else:
                # If password is null, check if username matches the provided password
                if username == password:
                    logging.info(f"User '{username}' logged in successfully with username as password.")
                    return jsonify({"message": "Login successful", "full_name": full_name, "username": username}), 200 # Return full_name and username
                else:
                    logging.warning(f"Failed login attempt for user '{username}': Password null, username-password mismatch.")
                    return jsonify({"error": "Invalid username or password"}), 401
        else:
            logging.warning(f"Failed login attempt: Username '{username}' not found.")
            return jsonify({"error": "Invalid username or password"}), 401

    except psycopg2.Error as e:
        logging.error(f"Database error during login: {e}")
        return jsonify({"error": "Database error during login."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during login: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/get_user_details/<string:username>', methods=['GET'])
def get_user_details(username):
    """Endpoint to retrieve a single user's details by username, excluding password."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, full_name, email, username, role, phone_number, status FROM users_data WHERE username = %s;", (username,))
        user = cur.fetchone()
        cur.close()

        if user:
            user_dict = dict(user)
            return jsonify(user_dict), 200
        else:
            return jsonify({"error": "User not found."}), 404

    except psycopg2.Error as e:
        logging.error(f"Database error during user details retrieval: {e}")
        return jsonify({"error": "Failed to retrieve user details due to a database error."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during user details retrieval: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/change_password', methods=['POST'])
def change_password():
    """Endpoint to change a user's password."""
    data = request.get_json()
    username = data.get('username')
    new_password = data.get('new_password')

    if not username or not new_password:
        return jsonify({"error": "Username and new password are required"}), 400

    # Password validation: 8 digits combo of string & int (assuming alphanumeric characters)
    if len(new_password) < 8 or not any(char.isdigit() for char in new_password) or not any(char.isalpha() for char in new_password):
        return jsonify({"error": "Password must be at least 8 characters long and contain a combination of letters and numbers."}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Hash the new password
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        update_query = "UPDATE users_data SET password = %s WHERE username = %s;"
        cur.execute(update_query, (hashed_password, username))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({"error": "User not found."}), 404

        cur.close()
        logging.info(f"Password for user '{username}' updated successfully.")
        return jsonify({"message": "Password updated successfully"}), 200

    except psycopg2.Error as e:
        conn.rollback()
        logging.error(f"Database error during password change: {e}")
        return jsonify({"error": "Failed to change password due to a database error."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during password change: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/check_user_exists', methods=['POST'])
def check_user_exists():
    """Endpoint to check if a user exists by username or email for password reset."""
    data = request.get_json()
    username_or_email = data.get('username_or_email')

    if not username_or_email:
        return jsonify({"error": "Username or email is required"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Check if the input is an email or username
        cur.execute("""
            SELECT username, email, full_name FROM users_data 
            WHERE username = %s OR email = %s;
        """, (username_or_email, username_or_email))
        
        user = cur.fetchone()
        cur.close()

        if user:
            return jsonify({
                "exists": True,
                "username": user['username'],
                "email": user['email'],
                "full_name": user['full_name']
            }), 200
        else:
            return jsonify({"exists": False}), 200

    except psycopg2.Error as e:
        logging.error(f"Database error during user existence check: {e}")
        return jsonify({"error": "Database error during user check."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during user existence check: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/reset_password', methods=['POST'])
def reset_password():
    """Endpoint to reset a user's password."""
    data = request.get_json()
    username = data.get('username')
    new_password = data.get('new_password')

    if not username or not new_password:
        return jsonify({"error": "Username and new password are required"}), 400

    # Password validation: 8 characters combo of string & int
    if len(new_password) < 8 or not any(char.isdigit() for char in new_password) or not any(char.isalpha() for char in new_password):
        return jsonify({"error": "Password must be at least 8 characters long and contain a combination of letters and numbers."}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Hash the new password
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        update_query = "UPDATE users_data SET password = %s WHERE username = %s;"
        cur.execute(update_query, (hashed_password, username))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({"error": "User not found."}), 404

        cur.close()
        logging.info(f"Password for user '{username}' reset successfully.")
        return jsonify({"message": "Password reset successfully"}), 200

    except psycopg2.Error as e:
        conn.rollback()
        logging.error(f"Database error during password reset: {e}")
        return jsonify({"error": "Failed to reset password due to a database error."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during password reset: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':

    app.run(port=5062, debug=True)
