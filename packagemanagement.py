import os
import psycopg2
import psycopg2.extras # Required for dictionary cursor
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS # Import CORS
import datetime
import uuid # For generating tracking_code if needed, or package_id
import logging # For better logging

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Configure basic logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)


DB_HOST = "dpg-d0skka6mcj7s73f3q86g-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_nq0m"
DB_USER = "shadowfly_nq0m_user"
DB_PASS = "vwnAIGWvfqTUxHZsJAXsoA8HAJNiTWo5"
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
                    weight_kg VARCHAR(50),  -- Consider using NUMERIC(10,2) or REAL for weight
                    assigned_drone_id VARCHAR(255),
                    estimated_arrival_time TIMESTAMP WITH TIME ZONE,
                    dispatch_time TIMESTAMP WITH TIME ZONE,
                    delivery_time VARCHAR(255), -- Consider TIMESTAMP WITH TIME ZONE or TEXT if it's not a structured time
                    last_known_lat DOUBLE PRECISION,
                    last_known_lng DOUBLE PRECISION,
                    last_update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    item_details VARCHAR(255)
                );
            """)
            conn.commit() # Crucial: commit after CREATE TABLE
            app.logger.info("packagemanagement table creation command executed and committed.")

            # Optional: Verify table creation by trying to count from it (good for debugging)
            # cur.execute("SELECT COUNT(*) FROM packagemanagement;")
            # app.logger.info(f"Verification: packagemanagement table exists and has {cur.fetchone()[0]} rows (initially).")

            # The primary key is already defined in the CREATE TABLE statement.
            # The previous block for checking and adding PK was redundant and has been removed.

        app.logger.info("Database initialization process completed successfully.")
    except psycopg2.Error as e:
        app.logger.critical(f"CRITICAL: Error during database initialization: {e}")
        app.logger.error(f"PGCODE: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'}")
        app.logger.error(f"PGERROR: {e.pgerror if hasattr(e, 'pgerror') else 'N/A'}")
        if conn:
            conn.rollback() # Rollback any partial transaction
    finally:
        if conn:
            conn.close()
            app.logger.info("Database connection closed after init_db.")

init_db()

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
        if field not in data or not data[field]: # Check for empty strings too
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
                    weight_kg, assigned_drone_id, estimated_arrival_time, dispatch_time,
                    delivery_time, last_known_lat, last_known_lng, item_details, last_update_time
                ) VALUES (
                    %(package_id)s, %(tracking_code)s, %(sender_id)s, %(customer_id)s, %(warehouse_name)s,
                    %(destination_address)s, %(destination_lat)s, %(destination_lng)s, %(current_status)s,
                    %(weight_kg)s, %(assigned_drone_id)s, %(estimated_arrival_time)s, %(dispatch_time)s,
                    %(delivery_time)s, %(last_known_lat)s, %(last_known_lng)s, %(item_details)s, CURRENT_TIMESTAMP
                ) RETURNING package_id;
            """, {
                "package_id": data.get('package_id'),
                "tracking_code": data.get('tracking_code'),
                "sender_id": data.get('sender_id'),
                "customer_id": data.get('customer_id'),
                "warehouse_name": data.get('warehouse_name'),
                "destination_address": data.get('destination_address'),
                "destination_lat": data.get('destination_lat', None), # Ensure None if not provided
                "destination_lng": data.get('destination_lng', None), # Ensure None if not provided
                "current_status": data.get('current_status', 'Pending'),
                "weight_kg": data.get('weight_kg'),
                "assigned_drone_id": data.get('assigned_drone_id'),
                "estimated_arrival_time": data.get('estimated_arrival_time', None), # Ensure None if not provided
                "dispatch_time": data.get('dispatch_time', None), # Ensure None if not provided
                "delivery_time": data.get('delivery_time'),
                "last_known_lat": data.get('last_known_lat', None), # Ensure None if not provided
                "last_known_lng": data.get('last_known_lng', None), # Ensure None if not provided
                "item_details": data.get('item_details')
            })
            new_package_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({"message": "Package created successfully", "package_id": new_package_id}), 201
    except psycopg2.Error as e:
        conn.rollback()
        error_message = f"Database error: {str(e)}"
        status_code = 500
        if hasattr(e, 'pgcode') and e.pgcode == '23505': # Unique violation
            status_code = 409
            constraint_name = e.diag.constraint_name if hasattr(e, 'diag') and hasattr(e.diag, 'constraint_name') else ''
            if 'packagemanagement_pkey' in constraint_name or 'package_id' in str(e).lower(): # Check constraint name or error string
                error_message = f"Package ID '{data.get('package_id')}' already exists. Detail: {e.diag.message_detail if hasattr(e, 'diag') else str(e)}"
            elif 'packagemanagement_tracking_code_key' in constraint_name or 'tracking_code' in str(e).lower(): # Check constraint name or error string
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

    set_clauses = []
    params = {"package_id_param": package_id, "last_update_time": datetime.datetime.now(datetime.timezone.utc)}

    allowed_fields = [
        'tracking_code', 'sender_id', 'customer_id', 'warehouse_name',
        'destination_address', 'destination_lat', 'destination_lng', 'current_status',
        'weight_kg', 'assigned_drone_id', 'estimated_arrival_time', 'dispatch_time',
        'delivery_time', 'last_known_lat', 'last_known_lng', 'item_details'
    ]
    
    for key in allowed_fields:
        if key in data: 
            # Allow setting fields to NULL if an empty string is explicitly passed for an optional field
            # For required fields, validation should happen at the client or be more strict here
            field_value = data[key]
            # psycopg2 uses None for SQL NULL.
            # If data[key] is an empty string for a field that can be NULL, convert to None.
            # For numeric/timestamp fields, ensure conversion or pass None.
            # This example assumes text-based fields can be empty or None.
            # For destination_lat/lng, last_known_lat/lng, estimated_arrival_time, dispatch_time:
            # if data[key] == "" or data[key] is None:
            # params[key] = None
            # else:
            # params[key] = data[key] # Ensure correct type conversion if needed
            
            # Simplified: if value is empty string, treat as None (if column allows NULL)
            # This behavior should be carefully considered based on column constraints (NOT NULL etc.)
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
            conn.commit()
            return jsonify({"message": "Package updated successfully", "package_id": updated_package[0]}), 200
    except psycopg2.Error as e:
        conn.rollback()
        error_message = f"Database error: {str(e)}"
        status_code = 500
        if hasattr(e, 'pgcode') and e.pgcode == '23505': # Unique constraint violation
            status_code = 409
            constraint_name = e.diag.constraint_name if hasattr(e, 'diag') and hasattr(e.diag, 'constraint_name') else ''
            # Check for tracking_code unique constraint. The default name is usually table_column_key
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
        with conn.cursor() as cur:
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
            # Assuming droneassignment table has a 'name' column for warehouse names
            cur.execute("SELECT DISTINCT name FROM droneassignment ORDER BY name;")
            warehouses = [row[0] for row in cur.fetchall() if row[0] is not None] # Filter out None names
            return jsonify(warehouses), 200
    except psycopg2.Error as e:
        # Check if the error is due to droneassignment table not existing
        if hasattr(e, 'pgcode') and e.pgcode == '42P01': # undefined_table
             app.logger.warning("Table 'droneassignment' not found. Cannot fetch warehouses. Ensure it is created.")
             return jsonify({"error": "Warehouse data source not available (droneassignment table missing). Please create it."}), 503 # Service Unavailable
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
             # Assuming droneassignment table has drone_id, drone_name, and name (for warehouse)
            cur.execute("SELECT drone_id, drone_name FROM droneassignment WHERE name = %s AND status = 'Active' ORDER BY drone_name;",
                (warehouse_name,))
            drones = cur.fetchall()
            return jsonify([dict(drone) for drone in drones]), 200
    except psycopg2.Error as e:
        if hasattr(e, 'pgcode') and e.pgcode == '42P01': # undefined_table
             app.logger.warning(f"Table 'droneassignment' not found. Cannot fetch drones for warehouse {warehouse_name}.")
             return jsonify({"error": f"Drone data source not available for warehouse {warehouse_name} (droneassignment table missing). Please create it."}), 503
        app.logger.error(f"Database error in get_drones_by_warehouse for {warehouse_name}: {str(e)}")
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
            # Assuming ddts table has latitude, longitude, and name columns
            cur.execute("SELECT latitude, longitude FROM ddts WHERE name = %s ;", (tower_name,))
            tower_location = cur.fetchone()
            if tower_location is None:
                return jsonify({"error": "Tower not found"}), 404
            return jsonify(dict(tower_location)), 200
    except psycopg2.Error as e:
        if hasattr(e, 'pgcode') and e.pgcode == '42P01': # undefined_table
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
            # Assuming ddts table has a 'name' column for tower names
            cur.execute("SELECT DISTINCT name FROM ddts where status = 'Active' ORDER BY name;")
            tower_names = [row[0] for row in cur.fetchall() if row[0] is not None] # Filter out None names
            return jsonify(tower_names), 200
    except psycopg2.Error as e:
        if hasattr(e, 'pgcode') and e.pgcode == '42P01': # undefined_table
            app.logger.warning("Table 'ddts' not found. Cannot fetch tower names. Please create it.")
            return jsonify({"error": "Tower names data source not available (ddts table missing). Please create it."}), 503
        app.logger.error(f"Database error in get_all_tower_names: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Ensure the logger is configured before running the app
    app.logger.info("Starting Flask application...")
    # The host '0.0.0.0' makes the server accessible externally (e.g., within Render's network)
    # Debug should ideally be False in production, but Render might manage this.
    app.run(debug=True, port=5000)