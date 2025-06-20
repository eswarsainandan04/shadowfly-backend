import psycopg2
import psycopg2.extras
import os
import logging
import hashlib
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Database connection details
DB_HOST = "dpg-d1aovm6uk2gs7390cttg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_um2n"
DB_USER = "shadowfly_um2n_user"
DB_PASS = "6ab9pofT8Tv0H5TqLWiD0qJZ0fTR8aNk"
DB_PORT = 5432

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        return None
    
    
    

def create_admins_table():
    """Create admins_data table if it doesn't exist"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS admins_data (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            mobile_number VARCHAR(15) NOT NULL,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        logger.info("Admins table created successfully or already exists")
        return True
    except psycopg2.Error as e:
        logger.error(f"Error creating table: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

create_admins_table()


@app.route('/api/admins', methods=['POST'])
def add_admin():
    """Add a new admin"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['name', 'email', 'mobile_number', 'username', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        # Validate email format
        import re
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, data['email']):
            return jsonify({'error': 'Invalid email format'}), 400

        # Validate mobile number (10 digits)
        if not re.match(r'^\d{10}$', data['mobile_number']):
            return jsonify({'error': 'Mobile number must be 10 digits'}), 400

        # Validate password length
        if len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters long'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Check if email or username already exists
        check_query = """
        SELECT id FROM admins_data
        WHERE email = %s OR username = %s
        """
        cursor.execute(check_query, (data['email'], data['username']))
        existing_admin = cursor.fetchone()

        if existing_admin:
            return jsonify({'error': 'Email or username already exists'}), 400

        # Hash the password
        hashed_password = hash_password(data['password'])

        # Insert new admin
        insert_query = """
        INSERT INTO admins_data (name, email, mobile_number, username, password)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """
        cursor.execute(insert_query, (
            data['name'],
            data['email'],
            data['mobile_number'],
            data['username'],
            hashed_password
        ))

        admin_id = cursor.fetchone()[0]
        conn.commit()

        logger.info(f"Admin added successfully with ID: {admin_id}")
        return jsonify({
            'message': 'Admin added successfully',
            'admin_id': admin_id
        }), 201

    except psycopg2.IntegrityError as e:
        conn.rollback()
        logger.error(f"Integrity error: {e}")
        return jsonify({'error': 'Email or username already exists'}), 400
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/admins', methods=['GET'])
def get_admins():
    """Get all admins (excluding passwords)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Select all admins except password field
        select_query = """
        SELECT id, name, email, mobile_number, username, created_at
        FROM admins_data
        ORDER BY created_at DESC
        """
        cursor.execute(select_query)
        admins = cursor.fetchall()

        # Convert to list of dictionaries
        admins_list = []
        for admin in admins:
            admin_dict = dict(admin)
            # Convert datetime to string if needed
            if admin_dict.get('created_at'):
                admin_dict['created_at'] = admin_dict['created_at'].isoformat()
            admins_list.append(admin_dict)

        return jsonify({
            'admins': admins_list,
            'count': len(admins_list)
        }), 200

    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/admins/<int:admin_id>', methods=['DELETE'])
def delete_admin(admin_id):
    """Delete an admin by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Check if admin exists
        check_query = "SELECT id FROM admins_data WHERE id = %s"
        cursor.execute(check_query, (admin_id,))
        admin = cursor.fetchone()

        if not admin:
            return jsonify({'error': 'Admin not found'}), 404

        # Delete the admin
        delete_query = "DELETE FROM admins_data WHERE id = %s"
        cursor.execute(delete_query, (admin_id,))
        conn.commit()

        logger.info(f"Admin with ID {admin_id} deleted successfully")
        return jsonify({'message': 'Admin deleted successfully'}), 200

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/admins/<int:admin_id>', methods=['PUT'])
def update_admin(admin_id):
    """Update an admin by ID"""
    try:
        data = request.get_json()

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Check if admin exists
        check_query = "SELECT id FROM admins_data WHERE id = %s"
        cursor.execute(check_query, (admin_id,))
        admin = cursor.fetchone()

        if not admin:
            return jsonify({'error': 'Admin not found'}), 404

        # Build update query dynamically based on provided fields
        update_fields = []
        update_values = []

        allowed_fields = ['name', 'email', 'mobile_number', 'username']
        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                update_values.append(data[field])

        # Handle password update separately
        if 'password' in data:
            if len(data['password']) < 6:
                return jsonify({'error': 'Password must be at least 6 characters long'}), 400
            update_fields.append("password = %s")
            update_values.append(hash_password(data['password']))

        if not update_fields:
            return jsonify({'error': 'No valid fields to update'}), 400

        update_values.append(admin_id)
        update_query = f"""
        UPDATE admins_data
        SET {', '.join(update_fields)}
        WHERE id = %s
        """

        cursor.execute(update_query, update_values)
        conn.commit()

        logger.info(f"Admin with ID {admin_id} updated successfully")
        return jsonify({'message': 'Admin updated successfully'}), 200

    except psycopg2.IntegrityError as e:
        conn.rollback()
        logger.error(f"Integrity error: {e}")
        return jsonify({'error': 'Email or username already exists'}), 400
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    """Handle admin login"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        # Hardcoded admin credentials check
        if username == "admin@shadowfly" and password == "drone12345":
            logger.info(f"Hardcoded admin '{username}' logged in successfully.")
            return jsonify({
                'message': 'Login successful',
                'username': username,
                'role': 'admin'
            }), 200

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Retrieve the hashed password for the given username from the database
        query = "SELECT id, username, password FROM admins_data WHERE username = %s"
        cursor.execute(query, (username,))
        admin = cursor.fetchone()

        if admin:
            # Hash the provided password and compare with the stored hashed password
            if hash_password(password) == admin['password']:
                logger.info(f"Admin '{username}' logged in successfully from database.")
                return jsonify({
                    'message': 'Login successful',
                    'username': admin['username'],
                    'role': 'admin'
                }), 200
            else:
                logger.warning(f"Invalid password attempt for username: {username}")
                return jsonify({'error': 'Invalid username or password'}), 401
        else:
            logger.warning(f"Login attempt with non-existent username: {username}")
            return jsonify({'error': 'Invalid username or password'}), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'An unexpected error occurred during login'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Admin API is running'}), 200

if __name__ == '__main__':
    # Create the admins table on startup
    create_admins_table()

    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5072)