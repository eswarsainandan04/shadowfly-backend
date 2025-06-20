import os
import csv
import io
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Database configuration
DB_HOST = "dpg-d1aovm6uk2gs7390cttg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_um2n"
DB_USER = "shadowfly_um2n_user"
DB_PASS = "6ab9pofT8Tv0H5TqLWiD0qJZ0fTR8aNk"
DB_PORT = 5432

def get_db_connection():
    """Establishes a connection to the PostgreSQL database and ensures the table exists."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT
        )
        # Create the updated table structure
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dronesdata (
                    id SERIAL PRIMARY KEY,
                    drone_id VARCHAR(225) UNIQUE NOT NULL,
                    drone_name VARCHAR(225) NOT NULL,
                    model VARCHAR(225),
                    drone_type VARCHAR(225),
                    weight DOUBLE PRECISION,
                    max_payload DOUBLE PRECISION,
                    battery_type VARCHAR(225),
                    battery_capacity VARCHAR(225),
                    gripper_01 VARCHAR(225),
                    gripper_02 VARCHAR(225),
                    gripper_03 VARCHAR(225),
                    camera_key VARCHAR(225),
                    communication_key VARCHAR(225),
                    status VARCHAR(50) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Add new columns to existing table if they don't exist
            try:
                cur.execute("ALTER TABLE dronesdata ADD COLUMN IF NOT EXISTS camera_key VARCHAR(225);")
                cur.execute("ALTER TABLE dronesdata ADD COLUMN IF NOT EXISTS communication_key VARCHAR(225);")
                cur.execute("ALTER TABLE dronesdata ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active';")
                cur.execute("ALTER TABLE dronesdata ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                cur.execute("ALTER TABLE dronesdata ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                
                # Rename max_playload to max_payload if it exists
                cur.execute("""
                    DO $$ 
                    BEGIN 
                        IF EXISTS(SELECT * FROM information_schema.columns WHERE table_name='dronesdata' AND column_name='max_playload') THEN
                            ALTER TABLE dronesdata RENAME COLUMN max_playload TO max_payload;
                        END IF;
                    END $$;
                """)
                
            except psycopg2.Error as e:
                print(f"Note: Columns may already exist or migration completed: {e}")
            
            # Create indexes for better performance
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dronesdata_drone_id ON dronesdata(drone_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dronesdata_status ON dronesdata(status);")
            
            conn.commit()
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL or creating table: {e}")
        return None
    

get_db_connection()



@app.route('/api/drones', methods=['GET'])
def get_drones_api():
    """Get all drones with enhanced data"""
    conn = get_db_connection()
    drones_list = []
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, drone_id, drone_name, model, drone_type,
                           weight, max_payload, battery_type, battery_capacity, 
                           gripper_01, gripper_02, gripper_03, camera_key, 
                           communication_key, status, created_at, updated_at
                    FROM dronesdata 
                    WHERE status != 'deleted'
                    ORDER BY created_at DESC
                """)
                raw_drones = cur.fetchall()
                if raw_drones:
                    columns = [desc[0].lower() for desc in cur.description]
                    drones_list = []
                    for row in raw_drones:
                        drone_dict = dict(zip(columns, row))
                        # Format timestamps
                        if drone_dict.get('created_at'):
                            drone_dict['created_at'] = drone_dict['created_at'].isoformat()
                        if drone_dict.get('updated_at'):
                            drone_dict['updated_at'] = drone_dict['updated_at'].isoformat()
                        drones_list.append(drone_dict)
        except psycopg2.Error as e:
            print(f"Error fetching drones for API: {e}")
            return jsonify({"error": f"Database error: {e}"}), 500
        finally:
            conn.close()
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500
    return jsonify(drones_list)

@app.route('/add_drone', methods=['POST'])
def add_drone():
    """Add a new drone with enhanced validation"""
    if request.method == 'POST':
        # Get form data
        drone_id_val = request.form.get('drone_id', '').strip()
        drone_name = request.form.get('drone_name', '').strip()
        model = request.form.get('model', '').strip()
        drone_type = request.form.get('drone_type', '').strip()
        weight_str = request.form.get('weight', '').strip()
        max_payload_str = request.form.get('max_payload', '').strip()
        battery_type = request.form.get('battery_type', '').strip()
        battery_capacity = request.form.get('battery_capacity', '').strip()
        camera_key = request.form.get('camera_key', '').strip()
        communication_key = request.form.get('communication_key', '').strip()

        # Validation
        if not drone_id_val or not drone_name:
            return jsonify({"message": "Drone ID and Drone Name are required.", "error": True}), 400

        # Parse numeric values
        weight = None
        if weight_str:
            try: 
                weight = float(weight_str)
                if weight < 0:
                    return jsonify({"message": "Weight must be a positive number.", "error": True}), 400
            except ValueError:
                return jsonify({"message": "Invalid input for Weight. Please enter a valid number.", "error": True}), 400
        
        max_payload = None
        if max_payload_str:
            try: 
                max_payload = float(max_payload_str)
                if max_payload < 0:
                    return jsonify({"message": "Max Payload must be a positive number.", "error": True}), 400
            except ValueError:
                return jsonify({"message": "Invalid input for Max Payload. Please enter a valid number.", "error": True}), 400

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Check for duplicate drone_id
                    cur.execute("SELECT id FROM dronesdata WHERE drone_id = %s AND status != 'deleted'", (drone_id_val,))
                    if cur.fetchone():
                        return jsonify({"message": f"Drone with ID '{drone_id_val}' already exists. Cannot add duplicate.", "error": True}), 409
                    
                    # Insert new drone
                    sql = """
                        INSERT INTO dronesdata (
                            drone_id, drone_name, model, drone_type, weight, max_payload, 
                            battery_type, battery_capacity, gripper_01, gripper_02, gripper_03, 
                            camera_key, communication_key, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s, %s, %s)
                        RETURNING id
                    """
                    cur.execute(sql, (
                        drone_id_val, drone_name, model or None, drone_type or None, 
                        weight, max_payload, battery_type or None, battery_capacity or None,
                        camera_key or None, communication_key or None, 'active'
                    ))
                    new_id = cur.fetchone()[0]
                    conn.commit()
                    return jsonify({
                        "message": "Drone added successfully!", 
                        "drone_id": drone_id_val,
                        "id": new_id
                    }), 201
                    
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Database error adding drone: {e}")
                return jsonify({"message": f"Error adding drone: {e}", "error": True}), 500
            finally:
                conn.close()
        else:
            return jsonify({"message": "Could not connect to the database to add drone.", "error": True}), 500
    
    return jsonify({"message": "Invalid request method.", "error": True}), 405

@app.route('/update_drone/<int:drone_db_id>', methods=['POST'])
def update_drone(drone_db_id):
    """Update an existing drone with enhanced validation"""
    if request.method == 'POST':
        # Get form data
        original_drone_id_val = request.form.get('original_drone_id', '').strip()
        drone_id_val = request.form.get('drone_id', '').strip()
        drone_name = request.form.get('drone_name', '').strip()
        model = request.form.get('model', '').strip()
        drone_type = request.form.get('drone_type', '').strip()
        weight_str = request.form.get('weight', '').strip()
        max_payload_str = request.form.get('max_payload', '').strip()
        battery_type = request.form.get('battery_type', '').strip()
        battery_capacity = request.form.get('battery_capacity', '').strip()
        camera_key = request.form.get('camera_key', '').strip()
        communication_key = request.form.get('communication_key', '').strip()

        # Validation
        if not drone_id_val or not drone_name:
            return jsonify({"message": "Drone ID and Drone Name are required.", "error": True}), 400
        
        # Parse numeric values
        weight = None
        if weight_str:
            try: 
                weight = float(weight_str)
                if weight < 0:
                    return jsonify({"message": "Weight must be a positive number.", "error": True}), 400
            except ValueError: 
                return jsonify({"message": "Invalid Weight. Must be a number.", "error": True}), 400
        
        max_payload = None
        if max_payload_str:
            try: 
                max_payload = float(max_payload_str)
                if max_payload < 0:
                    return jsonify({"message": "Max Payload must be a positive number.", "error": True}), 400
            except ValueError: 
                return jsonify({"message": "Invalid Max Payload. Must be a number.", "error": True}), 400

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Check if drone exists
                    cur.execute("SELECT drone_id FROM dronesdata WHERE id = %s AND status != 'deleted'", (drone_db_id,))
                    if not cur.fetchone():
                        return jsonify({"message": "Drone not found.", "error": True}), 404
                    
                    # Check for duplicate drone_id (excluding current drone)
                    if drone_id_val != original_drone_id_val:
                        cur.execute("SELECT id FROM dronesdata WHERE drone_id = %s AND id != %s AND status != 'deleted'", (drone_id_val, drone_db_id))
                        if cur.fetchone():
                            return jsonify({"message": f"Another drone with ID '{drone_id_val}' already exists. Update failed.", "error": True}), 409

                    # Update the drone record
                    sql = """
                        UPDATE dronesdata
                        SET drone_id = %s, drone_name = %s, model = %s, drone_type = %s,
                            weight = %s, max_payload = %s, battery_type = %s, battery_capacity = %s,
                            gripper_01 = NULL, gripper_02 = NULL, gripper_03 = NULL, 
                            camera_key = %s, communication_key = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s AND status != 'deleted'
                    """
                    cur.execute(sql, (
                        drone_id_val, drone_name, model or None, drone_type or None,
                        weight, max_payload, battery_type or None, battery_capacity or None,
                        camera_key or None, communication_key or None, drone_db_id
                    ))
                    
                    # Update related tables if drone_id changed
                    if drone_id_val != original_drone_id_val:
                        # Update packagemanagement table
                        try:
                            cur.execute("""
                                SELECT COUNT(*) FROM information_schema.tables 
                                WHERE table_name = 'packagemanagement'
                            """)
                            if cur.fetchone()[0] > 0:
                                cur.execute("""
                                    UPDATE packagemanagement 
                                    SET assigned_drone_id = %s 
                                    WHERE assigned_drone_id = %s
                                """, (drone_id_val, original_drone_id_val))
                                print(f"Updated packagemanagement table: {cur.rowcount} rows affected")
                        except psycopg2.Error as e:
                            print(f"Warning: Could not update packagemanagement table: {e}")
                        
                        # Update droneassignment table
                        try:
                            cur.execute("""
                                SELECT COUNT(*) FROM information_schema.tables 
                                WHERE table_name = 'droneassignment'
                            """)
                            if cur.fetchone()[0] > 0:
                                cur.execute("""
                                    UPDATE droneassignment 
                                    SET drone_id = %s, drone_name = %s 
                                    WHERE drone_id = %s
                                """, (drone_id_val, drone_name, original_drone_id_val))
                                print(f"Updated droneassignment table: {cur.rowcount} rows affected")
                        except psycopg2.Error as e:
                            print(f"Warning: Could not update droneassignment table: {e}")
                    
                    conn.commit()
                    return jsonify({"message": "Drone updated successfully!", "drone_db_id": drone_db_id}), 200
                    
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Database error updating drone: {e}")
                return jsonify({"message": f"Error updating drone: {e}", "error": True}), 500
            finally:
                conn.close()
        else:
            return jsonify({"message": "Could not connect to the database to update drone.", "error": True}), 500
    
    return jsonify({"message": "Invalid request method.", "error": True}), 405

@app.route('/delete_drone/<int:drone_db_id>', methods=['POST'])
def delete_drone(drone_db_id):
    """Soft delete a drone (mark as deleted instead of removing)"""
    print(f"Attempting to delete drone with DB ID: {drone_db_id}")
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # Check if drone exists
                cur.execute("SELECT drone_id FROM dronesdata WHERE id = %s AND status != 'deleted'", (drone_db_id,))
                drone_record = cur.fetchone()

                if drone_record is None:
                    print(f"Drone with Sys. ID {drone_db_id} not found.")
                    return jsonify({"message": f"Drone with Sys. ID {drone_db_id} not found.", "error": True}), 404

                drone_id_to_delete = drone_record[0]
                print(f"Found drone_id to delete: {drone_id_to_delete}")

                # Soft delete the drone (mark as deleted)
                cur.execute("""
                    UPDATE dronesdata 
                    SET status = 'deleted', updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (drone_db_id,))
                print(f"Marked drone {drone_db_id} as deleted")

                # Clean up related tables
                try:
                    # Delete from droneassignment table
                    cur.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_name = 'droneassignment'
                    """)
                    if cur.fetchone()[0] > 0:
                        cur.execute("DELETE FROM droneassignment WHERE drone_id = %s", (drone_id_to_delete,))
                        print(f"Deleted {cur.rowcount} rows from droneassignment table")
                except psycopg2.Error as e:
                    print(f"Warning: Could not delete from droneassignment table: {e}")

                # Update packagemanagement to set assigned_drone_id to null
                try:
                    cur.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_name = 'packagemanagement'
                    """)
                    if cur.fetchone()[0] > 0:
                        cur.execute("UPDATE packagemanagement SET assigned_drone_id = null WHERE assigned_drone_id = %s", (drone_id_to_delete,))
                        print(f"Updated {cur.rowcount} rows in packagemanagement table (set assigned_drone_id to null)")
                except psycopg2.Error as e:
                    print(f"Warning: Could not update packagemanagement table: {e}")

            conn.commit()
            print(f"Drone {drone_db_id} deleted successfully and related records updated!")
            return jsonify({"message": f"Drone {drone_db_id} deleted successfully and related records updated!"}), 200
            
        except psycopg2.Error as e:
            conn.rollback()
            print(f"Database error deleting drone: {e}")
            return jsonify({"message": f"Error deleting drone: {e}", "error": True}), 500
        finally:
            if conn:
                conn.close()
    else:
        print("Could not connect to the database to delete drone.")
        return jsonify({"message": "Could not connect to the database to delete drone.", "error": True}), 500

# New endpoints for drone assignment operations
@app.route('/update_drone_assignment', methods=['POST'])
def update_drone_assignment():
    """Update drone assignment in packagemanagement and droneassignment tables"""
    try:
        data = request.get_json()
        new_drone_id = data.get('new_drone_id')
        old_drone_id = data.get('old_drone_id')
        drone_name = data.get('drone_name')
        
        if not new_drone_id or not old_drone_id:
            return jsonify({"message": "Both new_drone_id and old_drone_id are required.", "error": True}), 400
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Update packagemanagement table
                    cur.execute("""
                        UPDATE packagemanagement 
                        SET assigned_drone_id = %s 
                        WHERE assigned_drone_id = %s
                    """, (new_drone_id, old_drone_id))
                    package_rows_updated = cur.rowcount
                    
                    # Update droneassignment table
                    if drone_name:
                        cur.execute("""
                            UPDATE droneassignment 
                            SET drone_id = %s, drone_name = %s 
                            WHERE drone_id = %s
                        """, (new_drone_id, drone_name, old_drone_id))
                    else:
                        cur.execute("""
                            UPDATE droneassignment 
                            SET drone_id = %s 
                            WHERE drone_id = %s
                        """, (new_drone_id, old_drone_id))
                    assignment_rows_updated = cur.rowcount
                    
                    conn.commit()
                    return jsonify({
                        "message": f"Drone assignment updated successfully! Updated {package_rows_updated} package records and {assignment_rows_updated} assignment records.",
                        "package_rows_updated": package_rows_updated,
                        "assignment_rows_updated": assignment_rows_updated
                    }), 200
                    
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Database error updating drone assignment: {e}")
                return jsonify({"message": f"Error updating drone assignment: {e}", "error": True}), 500
            finally:
                conn.close()
        else:
            return jsonify({"message": "Could not connect to the database.", "error": True}), 500
            
    except Exception as e:
        return jsonify({"message": f"Error processing request: {e}", "error": True}), 500

@app.route('/delete_drone_assignment', methods=['POST'])
def delete_drone_assignment():
    """Delete drone assignment and update related records"""
    try:
        data = request.get_json()
        drone_id = data.get('drone_id')
        
        if not drone_id:
            return jsonify({"message": "drone_id is required.", "error": True}), 400
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Delete from droneassignment table
                    cur.execute("DELETE FROM droneassignment WHERE drone_id = %s", (drone_id,))
                    assignment_rows_deleted = cur.rowcount
                    
                    # Update packagemanagement to set assigned_drone_id to null
                    cur.execute("UPDATE packagemanagement SET assigned_drone_id = null WHERE assigned_drone_id = %s", (drone_id,))
                    package_rows_updated = cur.rowcount
                    
                    conn.commit()
                    return jsonify({
                        "message": f"Drone assignment deleted successfully! Deleted {assignment_rows_deleted} assignment records and updated {package_rows_updated} package records.",
                        "assignment_rows_deleted": assignment_rows_deleted,
                        "package_rows_updated": package_rows_updated
                    }), 200
                    
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Database error deleting drone assignment: {e}")
                return jsonify({"message": f"Error deleting drone assignment: {e}", "error": True}), 500
            finally:
                conn.close()
        else:
            return jsonify({"message": "Could not connect to the database.", "error": True}), 500
            
    except Exception as e:
        return jsonify({"message": f"Error processing request: {e}", "error": True}), 500

@app.route('/export_csv')
def export_csv():
    """Export drones to CSV with enhanced data"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection failed, cannot export CSV.", "error": True}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT drone_id, drone_name, model, drone_type, weight, max_payload, 
                       battery_type, battery_capacity, camera_key, communication_key, 
                       status, created_at, updated_at
                FROM dronesdata 
                WHERE status != 'deleted'
                ORDER BY created_at DESC
            """)
            rows = cur.fetchall()
            column_names = [desc[0] for desc in cur.description]

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(column_names)
        
        # Format rows for CSV export
        formatted_rows = []
        for row in rows:
            formatted_row = []
            for item in row:
                if isinstance(item, datetime):
                    formatted_row.append(item.isoformat())
                else:
                    formatted_row.append(item)
            formatted_rows.append(formatted_row)
        
        cw.writerows(formatted_rows)
        output = si.getvalue()
        si.close()
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=drones_export.csv"}
        )
    except psycopg2.Error as e:
        print(f"Error exporting CSV: {e}")
        return jsonify({"message": f"Error exporting CSV: {e}", "error": True}), 500
    finally:
        if conn:
            conn.close()

@app.route('/import_csv', methods=['POST'])
def import_csv():
    """Import drones from CSV with enhanced validation"""
    if 'csv_file' not in request.files:
        return jsonify({'message': 'No file part in the request.', 'error': True}), 400

    file = request.files['csv_file']
    if file.filename == '':
        return jsonify({'message': 'No file selected for uploading.', 'error': True}), 400

    if file and file.filename.endswith('.csv'):
        conn = get_db_connection()
        if not conn:
            return jsonify({'message': "Database connection failed, cannot import CSV.", 'error': True}), 500
        
        imported_count = 0
        skipped_count = 0
        error_count = 0
        expected_headers = [
            'drone_id', 'drone_name', 'model', 'drone_type', 'weight', 'max_payload', 
            'battery_type', 'battery_capacity', 'camera_key', 'communication_key'
        ]
        messages = []

        try:
            stream = io.TextIOWrapper(file.stream, encoding='utf-8', newline='')
            csv_reader = csv.reader(stream)
            header = next(csv_reader)
            
            # Flexible header matching
            header_lower = [h.strip().lower() for h in header] if header else []
            expected_lower = [h.lower() for h in expected_headers]
            
            # Check if essential headers are present
            essential_headers = ['drone_id', 'drone_name']
            missing_essential = [h for h in essential_headers if h not in header_lower]
            if missing_essential:
                return jsonify({
                    "message": f"CSV file is missing essential headers: {', '.join(missing_essential)}. Please ensure drone_id and drone_name columns are present.",
                    "error": True
                }), 400

            with conn.cursor() as cur:
                for row_number, row in enumerate(csv_reader, start=2):
                    if not row or all(not cell.strip() for cell in row):
                        continue  # Skip empty rows
                    
                    # Create a flexible mapping
                    row_data = {}
                    for i, cell in enumerate(row):
                        if i < len(header):
                            key = header[i].strip().lower()
                            row_data[key] = cell.strip() if cell else ''
                    
                    # Extract required fields
                    drone_id_val = row_data.get('drone_id', '').strip()
                    drone_name = row_data.get('drone_name', '').strip()
                    
                    if not drone_id_val or not drone_name:
                        messages.append(f"Row {row_number}: Drone ID or Drone Name is missing. Skipping.")
                        skipped_count += 1
                        continue

                    # Check for existing drone
                    cur.execute("SELECT id FROM dronesdata WHERE drone_id = %s AND status != 'deleted'", (drone_id_val,))
                    if cur.fetchone():
                        messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): Already exists. Skipping.")
                        skipped_count += 1
                        continue
                    
                    # Parse and validate numeric fields
                    weight = None
                    weight_str = row_data.get('weight', '').strip()
                    if weight_str:
                        try: 
                            weight = float(weight_str)
                            if weight < 0:
                                messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): Weight must be positive. Skipping.")
                                skipped_count += 1
                                continue
                        except ValueError: 
                            messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): Invalid weight value '{weight_str}'. Skipping.")
                            skipped_count += 1
                            continue
                    
                    max_payload = None
                    max_payload_str = row_data.get('max_payload', '').strip()
                    if max_payload_str:
                        try: 
                            max_payload = float(max_payload_str)
                            if max_payload < 0:
                                messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): Max payload must be positive. Skipping.")
                                skipped_count += 1
                                continue
                        except ValueError:
                            messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): Invalid max_payload value '{max_payload_str}'. Skipping.")
                            skipped_count += 1
                            continue
                    
                    # Extract other fields
                    model = row_data.get('model', '').strip() or None
                    drone_type = row_data.get('drone_type', '').strip() or None
                    battery_type = row_data.get('battery_type', '').strip() or None
                    battery_capacity = row_data.get('battery_capacity', '').strip() or None
                    camera_key = row_data.get('camera_key', '').strip() or None
                    communication_key = row_data.get('communication_key', '').strip() or None

                    try:
                        sql = """
                            INSERT INTO dronesdata (
                                drone_id, drone_name, model, drone_type, weight, max_payload, 
                                battery_type, battery_capacity, gripper_01, gripper_02, gripper_03, 
                                camera_key, communication_key, status
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s, %s, %s)
                        """
                        cur.execute(sql, (
                            drone_id_val, drone_name, model, drone_type, weight, max_payload, 
                            battery_type, battery_capacity, camera_key, communication_key, 'active'
                        ))
                        imported_count += 1
                    except psycopg2.Error as db_err:
                        messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): DB error: {db_err}. Skipping.")
                        error_count += 1
                        conn.rollback()
                    
                conn.commit()
            
            summary_message = f"CSV Import Complete: {imported_count} rows imported, {skipped_count} skipped, {error_count} DB errors."
            messages.insert(0, summary_message)
            return jsonify({
                "message": "\n".join(messages), 
                "imported_count": imported_count, 
                "skipped_count": skipped_count, 
                "error_count": error_count
            }), 200

        except Exception as e:
            if conn: 
                conn.rollback()
            print(f"Error processing CSV file: {e}")
            return jsonify({"message": f"Error processing CSV file: {e}", "error": True}), 500
        finally:
            if conn:
                conn.close()
    else:
        return jsonify({'message': 'Invalid file type. Please upload a .csv file.', 'error': True}), 400

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            return jsonify({"status": "healthy", "database": "connected"}), 200
        else:
            return jsonify({"status": "unhealthy", "database": "disconnected"}), 503
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5014, debug=True)
