import os
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import logging

app = Flask(__name__)
CORS(app)

# Configure basic logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

DB_HOST = "dpg-d1aovm6uk2gs7390cttg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_um2n"
DB_USER = "shadowfly_um2n_user"
DB_PASS = "6ab9pofT8Tv0H5TqLWiD0qJZ0fTR8aNk"
DB_PORT = 5432

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        app.logger.info("Database connection established successfully.")
        return conn
    except psycopg2.Error as e:
        app.logger.error(f"Error connecting to PostgreSQL: {e}")
        return None

def init_db():
    """Initializes the database by creating the packagemanagement table if it doesn't exist."""
    app.logger.info("Attempting to initialize database...")
    conn = get_db_connection()
    if conn is None:
        app.logger.critical("CRITICAL: Database connection failed in init_db. Table initialization skipped.")
        return

    try:
        with conn.cursor() as cur:
            app.logger.info("Successfully connected to database for init_db. Attempting to create packagemanagement table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS packagemanagement (
                    package_id VARCHAR(255) PRIMARY KEY,
                    tracking_code VARCHAR(255) UNIQUE NOT NULL,
                    sender_id VARCHAR(255),
                    customer_id VARCHAR(255),
                    warehouse_name VARCHAR(255),
                    destination_address TEXT,
                    destination_lat DOUBLE PRECISION,
                    destination_lng DOUBLE PRECISION,
                    current_status VARCHAR(50) DEFAULT 'Pending',
                    weight_kg VARCHAR(50),
                    assigned_drone_id VARCHAR(255),
                    assigned_gripper VARCHAR(255),
                    estimated_arrival_time TIMESTAMP WITH TIME ZONE,
                    dispatch_time TIMESTAMP WITH TIME ZONE,
                    delivery_time VARCHAR(255),
                    last_known_lat DOUBLE PRECISION,
                    last_known_lng DOUBLE PRECISION,
                    last_update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    item_details VARCHAR(255)
                );
            """)
            conn.commit()
            app.logger.info("packagemanagement table creation command executed and committed.")
        app.logger.info("Database initialization process completed successfully.")
    except psycopg2.Error as e:
        app.logger.critical(f"CRITICAL: Error during database initialization: {e}")
        app.logger.error(f"PGCODE: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'}")
        app.logger.error(f"PGERROR: {e.pgerror if hasattr(e, 'pgerror') else 'N/A'}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            app.logger.info("Database connection closed after init_db.")

# Call init_db() when the application starts
init_db()

def update_drone_gripper(conn, drone_id, gripper_field, package_id):
    """Updates the specified gripper field in the dronesdata table."""
    if not drone_id or not gripper_field:
        return False
    
    try:
        with conn.cursor() as cur:
            # Update the specified gripper field with the package_id
            cur.execute(f"""
                UPDATE dronesdata 
                SET {gripper_field} = %s 
                WHERE drone_id = %s;
            """, (package_id, drone_id))
            rows_affected = cur.rowcount
            app.logger.info(f"Updated {gripper_field} for drone {drone_id} with package {package_id}. Rows affected: {rows_affected}")
            return rows_affected > 0
    except psycopg2.Error as e:
        app.logger.error(f"Error updating drone gripper: {e}")
        return False

def clear_drone_gripper(conn, package_id):
    """Clears the gripper field in dronesdata table that contains the specified package_id."""
    if not package_id:
        return False
    
    try:
        with conn.cursor() as cur:
            # Find and clear any gripper fields that contain this package_id
            for gripper_field in ['gripper_01', 'gripper_02', 'gripper_03']:
                cur.execute(f"""
                    UPDATE dronesdata 
                    SET {gripper_field} = NULL 
                    WHERE {gripper_field} = %s;
                """, (package_id,))
            
            conn.commit()
            app.logger.info(f"Cleared package {package_id} from any drone grippers")
            return True
    except psycopg2.Error as e:
        app.logger.error(f"Error clearing drone gripper: {e}")
        conn.rollback()
        return False

@app.route('/')
def index():
    """Serves the main HTML page (if you have one served by Flask)."""
    return "Flask Backend for Package Management is Running"

@app.route('/api/packages', methods=['POST'])
def create_package():
    """Creates a new package."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    required_fields = ['package_id', 'tracking_code', 'sender_id', 'customer_id', 'destination_address', 'weight_kg']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Missing or empty required field: {field}"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO packagemanagement (
                    package_id, tracking_code, sender_id, customer_id, warehouse_name,
                    destination_address, destination_lat, destination_lng, current_status,
                    weight_kg, assigned_drone_id, assigned_gripper, estimated_arrival_time, dispatch_time,
                    delivery_time, last_known_lat, last_known_lng, item_details, last_update_time
                ) VALUES (
                    %(package_id)s, %(tracking_code)s, %(sender_id)s, %(customer_id)s, %(warehouse_name)s,
                    %(destination_address)s, %(destination_lat)s, %(destination_lng)s, %(current_status)s,
                    %(weight_kg)s, %(assigned_drone_id)s, %(assigned_gripper)s, %(estimated_arrival_time)s, %(dispatch_time)s,
                    %(delivery_time)s, %(last_known_lat)s, %(last_known_lng)s, %(item_details)s, CURRENT_TIMESTAMP
                ) RETURNING package_id;
            """, {
                "package_id": data.get('package_id'),
                "tracking_code": data.get('tracking_code'),
                "sender_id": data.get('sender_id'),
                "customer_id": data.get('customer_id'),
                "warehouse_name": data.get('warehouse_name'),
                "destination_address": data.get('destination_address'),
                "destination_lat": data.get('destination_lat', None),
                "destination_lng": data.get('destination_lng', None),
                "current_status": data.get('current_status', 'Pending'),
                "weight_kg": data.get('weight_kg'),
                "assigned_drone_id": data.get('assigned_drone_id'),
                "assigned_gripper": data.get('assigned_gripper'),
                "estimated_arrival_time": data.get('estimated_arrival_time', None),
                "dispatch_time": data.get('dispatch_time', None),
                "delivery_time": data.get('delivery_time'),
                "last_known_lat": data.get('last_known_lat', None),
                "last_known_lng": data.get('last_known_lng', None),
                "item_details": data.get('item_details'),
            })
            new_package_id = cur.fetchone()[0]
            
            # Update drone gripper if assigned
            if data.get('assigned_drone_id') and data.get('assigned_gripper'):
                update_drone_gripper(conn, data.get('assigned_drone_id'), data.get('assigned_gripper'), data.get('package_id'))
            
            conn.commit()
            return jsonify({"message": "Package created successfully", "package_id": new_package_id}), 201
    except psycopg2.Error as e:
        conn.rollback()
        error_message = f"Database error: {str(e)}"
        status_code = 500
        if hasattr(e, 'pgcode') and e.pgcode == '23505':
            status_code = 409
            constraint_name = e.diag.constraint_name if hasattr(e, 'diag') and hasattr(e.diag, 'constraint_name') else ''
            if 'packagemanagement_pkey' in constraint_name or 'package_id' in str(e).lower():
                error_message = f"Package ID '{data.get('package_id')}' already exists. Detail: {e.diag.message_detail if hasattr(e, 'diag') else str(e)}"
            elif 'packagemanagement_tracking_code_key' in constraint_name or 'tracking_code' in str(e).lower():
                error_message = f"Tracking Code '{data.get('tracking_code')}' already exists. Detail: {e.diag.message_detail if hasattr(e, 'diag') else str(e)}"
            else:
                error_message = f"A unique field already exists. Detail: {e.diag.message_detail if hasattr(e, 'diag') else str(e)}"
        app.logger.error(f"Error in create_package: {error_message} (PGCode: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'})")
        return jsonify({"error": error_message}), status_code
    finally:
        if conn:
            conn.close()

@app.route('/api/packages', methods=['GET'])
def get_all_packages():
    """Retrieves all packages."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM packagemanagement ORDER BY last_update_time DESC;")
            packages = cur.fetchall()
            result = []
            for package in packages:
                pkg_dict = dict(package)
                for key, value in pkg_dict.items():
                    if isinstance(value, datetime.datetime):
                        pkg_dict[key] = value.isoformat()
                result.append(pkg_dict)
            return jsonify(result), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error in get_all_packages: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/packages/<package_id>', methods=['GET'])
def get_package(package_id):
    """Retrieves a specific package by its ID."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM packagemanagement WHERE package_id = %s;", (package_id,))
            package = cur.fetchone()
            if package is None:
                return jsonify({"error": "Package not found"}), 404
            
            pkg_dict = dict(package)
            for key, value in pkg_dict.items():
                if isinstance(value, datetime.datetime):
                    pkg_dict[key] = value.isoformat()
            return jsonify(pkg_dict), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error in get_package for {package_id}: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/packages/<package_id>', methods=['PUT'])
def update_package(package_id):
    """Updates an existing package."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    # First, get the current package data to check if gripper assignment changed
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT assigned_drone_id, assigned_gripper FROM packagemanagement WHERE package_id = %s;", (package_id,))
            current_package = cur.fetchone()
            if current_package is None:
                return jsonify({"error": "Package not found"}), 404
            
            current_drone_id = current_package['assigned_drone_id']
            current_gripper = current_package['assigned_gripper']
    except psycopg2.Error as e:
        app.logger.error(f"Error fetching current package data: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    set_clauses = []
    params = {"package_id_param": package_id, "last_update_time": datetime.datetime.now(datetime.timezone.utc)}

    allowed_fields = [
        'tracking_code', 'sender_id', 'customer_id', 'warehouse_name',
        'destination_address', 'destination_lat', 'destination_lng', 'current_status',
        'weight_kg', 'assigned_drone_id', 'assigned_gripper', 'estimated_arrival_time', 'dispatch_time',
        'delivery_time', 'last_known_lat', 'last_known_lng', 'item_details', 
    ]
    
    for key in allowed_fields:
        if key in data: 
            params[key] = data[key] if data[key] != "" else None
            set_clauses.append(f"{key} = %({key})s")

    if not set_clauses:
        return jsonify({"error": "No update fields provided"}), 400

    set_clauses.append("last_update_time = %(last_update_time)s")
    query = f"UPDATE packagemanagement SET {', '.join(set_clauses)} WHERE package_id = %(package_id_param)s RETURNING package_id;"

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            updated_package = cur.fetchone()
            if updated_package is None:
                return jsonify({"error": "Package not found or no change made"}), 404
            
            # Handle gripper assignment changes
            new_drone_id = data.get('assigned_drone_id')
            new_gripper = data.get('assigned_gripper')
            
            # If gripper assignment changed, update dronesdata table
            if 'assigned_gripper' in data or 'assigned_drone_id' in data:
                # Clear previous assignment if it existed
                if current_gripper and current_drone_id:
                    update_drone_gripper(conn, current_drone_id, current_gripper, None)
                
                # Set new assignment if provided
                if new_gripper and new_drone_id:
                    update_drone_gripper(conn, new_drone_id, new_gripper, package_id)
            
            conn.commit()
            return jsonify({"message": "Package updated successfully", "package_id": updated_package[0]}), 200
    except psycopg2.Error as e:
        conn.rollback()
        error_message = f"Database error: {str(e)}"
        status_code = 500
        if hasattr(e, 'pgcode') and e.pgcode == '23505':
            status_code = 409
            constraint_name = e.diag.constraint_name if hasattr(e, 'diag') and hasattr(e.diag, 'constraint_name') else ''
            if 'packagemanagement_tracking_code_key' in constraint_name or 'tracking_code' in str(e).lower():
                 error_message = f"Update failed: Tracking Code '{data.get('tracking_code', params.get('tracking_code'))}' already exists. Detail: {e.diag.message_detail if hasattr(e, 'diag') else str(e)}"
            else:
                error_message = f"Update failed due to a unique constraint violation. Detail: {e.diag.message_detail if hasattr(e, 'diag') else str(e)}"
        
        app.logger.error(f"Error in update_package for {package_id}: {error_message} (PGCode: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'})")
        return jsonify({"error": error_message}), status_code
    finally:
        if conn:
            conn.close()

@app.route('/api/packages/<package_id>', methods=['DELETE'])
def delete_package(package_id):
    """Deletes a package."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        # First, get the current package data to check if it has a gripper assignment
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT assigned_drone_id, assigned_gripper FROM packagemanagement WHERE package_id = %s;", (package_id,))
            current_package = cur.fetchone()
            if current_package is None:
                return jsonify({"error": "Package not found"}), 404
            
            current_drone_id = current_package['assigned_drone_id']
            current_gripper = current_package['assigned_gripper']
            
            # Clear gripper assignment if it exists
            if current_gripper and current_drone_id:
                update_drone_gripper(conn, current_drone_id, current_gripper, None)
            
            # Delete the package
            cur.execute("DELETE FROM packagemanagement WHERE package_id = %s RETURNING package_id;", (package_id,))
            deleted_package = cur.fetchone()
            if deleted_package is None:
                return jsonify({"error": "Package not found"}), 404
            
            conn.commit()
            return jsonify({"message": "Package deleted successfully", "package_id": deleted_package[0]}), 200
    except psycopg2.Error as e:
        conn.rollback()
        app.logger.error(f"Database error in delete_package for {package_id}: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/warehouses', methods=['GET'])
def get_warehouses():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT name FROM droneassignment ORDER BY name;")
            warehouses = [row[0] for row in cur.fetchall() if row[0] is not None]
            return jsonify(warehouses), 200
    except psycopg2.Error as e:
        if hasattr(e, 'pgcode') and e.pgcode == '42P01':
             app.logger.warning("Table 'droneassignment' not found. Cannot fetch warehouses. Ensure it is created.")
             return jsonify({"error": "Warehouse data source not available (droneassignment table missing). Please create it."}), 503
        app.logger.error(f"Database error in get_warehouses: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/drones/<warehouse_name>', methods=['GET'])
def get_drones_by_warehouse(warehouse_name):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT drone_id, drone_name FROM droneassignment WHERE name = %s AND status = 'Active' ORDER BY drone_name;",
                (warehouse_name,))
            drones = cur.fetchall()
            return jsonify([dict(drone) for drone in drones]), 200
    except psycopg2.Error as e:
        if hasattr(e, 'pgcode') and e.pgcode == '42P01':
             app.logger.warning(f"Table 'droneassignment' not found. Cannot fetch drones for warehouse {warehouse_name}.")
             return jsonify({"error": f"Drone data source not available for warehouse {warehouse_name} (droneassignment table missing). Please create it."}), 503
        app.logger.error(f"Database error in get_drones_by_warehouse for {warehouse_name}: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/drone-grippers/<drone_id>', methods=['GET'])
def get_drone_grippers(drone_id):
    """Retrieves gripper information for a specific drone."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT gripper_01, gripper_02, gripper_03 
                FROM dronesdata 
                WHERE drone_id = %s;
            """, (drone_id,))
            gripper_data = cur.fetchone()
            if gripper_data is None:
                return jsonify({"error": "Drone not found"}), 404
            
            return jsonify(dict(gripper_data)), 200
    except psycopg2.Error as e:
        if hasattr(e, 'pgcode') and e.pgcode == '42P01':
            app.logger.warning(f"Table 'dronesdata' not found. Cannot fetch gripper data for drone {drone_id}.")
            return jsonify({"error": f"Drone gripper data source not available (dronesdata table missing). Please create it."}), 503
        app.logger.error(f"Database error in get_drone_grippers for {drone_id}: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/towers/<tower_name>', methods=['GET'])
def get_tower_location(tower_name):
    """Retrieves latitude and longitude for a given tower name from the ddts table."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT latitude, longitude FROM ddts WHERE name = %s;", (tower_name,))
            tower_location = cur.fetchone()
            if tower_location is None:
                return jsonify({"error": "Tower not found"}), 404
            return jsonify(dict(tower_location)), 200
    except psycopg2.Error as e:
        if hasattr(e, 'pgcode') and e.pgcode == '42P01':
            app.logger.warning(f"Table 'ddts' not found. Cannot fetch tower location for {tower_name}.")
            return jsonify({"error": f"Tower location data source not available for {tower_name} (ddts table missing). Please create it."}), 503
        app.logger.error(f"Database error in get_tower_location for {tower_name}: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/towers', methods=['GET'])
def get_all_tower_names():
    """Retrieves all distinct tower names from the ddts table."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT name FROM ddts WHERE status = 'Active' ORDER BY name;")
            tower_names = [row[0] for row in cur.fetchall() if row[0] is not None]
            return jsonify(tower_names), 200
    except psycopg2.Error as e:
        if hasattr(e, 'pgcode') and e.pgcode == '42P01':
            app.logger.warning("Table 'ddts' not found. Cannot fetch tower names. Please create it.")
            return jsonify({"error": "Tower names data source not available (ddts table missing). Please create it."}), 503
        app.logger.error(f"Database error in get_all_tower_names: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.logger.info("Starting Flask application...")
    app.run(debug=True, port=5024)
