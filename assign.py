import os
import psycopg2
from flask import Flask, request, jsonify # Added jsonify
import datetime
from flask_cors import CORS # Added CORS

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing requests from your React app

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
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        return None

# API Endpoint to get drones
@app.route('/api/drones', methods=['GET'])
def get_drones():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Could not connect to the database."}), 500

    drones_list = []
    try:
        with conn.cursor() as cur:
            # Assuming drone_id is the primary key in dronesdata
            cur.execute("SELECT drone_id, drone_name, model FROM dronesdata ORDER BY drone_name") #
            drones_data = cur.fetchall()
            for row in drones_data:
                # React expects 'id' for key/value.
                # Using drone_id as the unique identifier from the dronesdata table.
                drones_list.append({'id': row[0], 'drone_id': row[0], 'drone_name': row[1], 'model': row[2]}) #
    except psycopg2.Error as e:
        print(f"Error fetching drones: {e}")
        return jsonify({"error": f"Error fetching drones from database: {e}"}), 500
    finally:
        if conn:
            conn.close()
    return jsonify(drones_list)

# API Endpoint to get warehouses
@app.route('/api/warehouses', methods=['GET'])
def get_warehouses():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Could not connect to the database."}), 500

    warehouses_list = []
    try:
        with conn.cursor() as cur:
            # Assuming 'id' is the primary key in warehouses
            cur.execute("SELECT id, name, latitude, longitude FROM warehouses ORDER BY name") #
            warehouses_data = cur.fetchall()
            for row in warehouses_data:
                warehouses_list.append({'id': row[0], 'name': row[1], 'latitude': row[2], 'longitude': row[3]}) #
    except psycopg2.Error as e:
        print(f"Error fetching warehouses: {e}")
        return jsonify({"error": f"Error fetching warehouses from database: {e}"}), 500
    finally:
        if conn:
            conn.close()
    return jsonify(warehouses_list)

# API Endpoint to get assignments
@app.route('/api/assignments', methods=['GET'])
def get_assignments():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Could not connect to the database."}), 500

    assignments_list = []
    try:
        with conn.cursor() as cur:
            # Changed da.longitude to da.logitude in the SQL query
            cur.execute("""
                SELECT da.id, da.drone_id, da.drone_name, da.name as warehouse_name,
                       da.latitude, da.longitude, da.status
                FROM droneassignment da
                ORDER BY da.drone_id ASC
            """) #
            assignments_data = cur.fetchall()
            for row in assignments_data:
                assignments_list.append({
                    'id': row[0], #
                    'drone_id': row[1], #
                    'drone_name': row[2], #
                    'warehouse_name': row[3], #
                    'latitude': row[4], #
                    'longitude': row[5], # row[5] now correctly fetches from da.logitude #
                    'status': row[6] #
                })
    except psycopg2.Error as e:
        print(f"Error fetching assignments: {e}")
        return jsonify({"error": f"Error fetching assignments from database: {e}"}), 500
    finally:
        if conn:
            conn.close()
    return jsonify(assignments_list)

# API Endpoint to assign a drone
@app.route('/api/assign', methods=['POST'])
def api_assign_drone():
    selected_drone_pk = request.form.get('drone_pk') #
    selected_warehouse_pk = request.form.get('warehouse_pk') #
    status = request.form.get('status') #

    if not selected_drone_pk or not selected_warehouse_pk or not status: #
        return jsonify({"message": "Error: Drone, warehouse, and status must be selected/provided.", "category": "warning"}), 400 #

    if status not in ['Active', 'Inactive']: #
        return jsonify({"message": "Error: Invalid status value. Must be 'Active' or 'Inactive'.", "category": "warning"}), 400 #

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error: Could not connect to the database for assignment.", "category": "error"}), 500 #

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT drone_name FROM dronesdata WHERE drone_id = %s", (selected_drone_pk,)) #
            drone_record = cur.fetchone() #
            if not drone_record:
                return jsonify({"message": f"Error: Drone with ID {selected_drone_pk} not found.", "category": "error"}), 404 #
            drone_name = drone_record[0] #

            cur.execute("SELECT name, latitude, longitude FROM warehouses WHERE id = %s", (int(selected_warehouse_pk),)) #
            warehouse_record = cur.fetchone() #
            if not warehouse_record:
                return jsonify({"message": f"Error: Warehouse with ID {selected_warehouse_pk} not found.", "category": "error"}), 404 #
            warehouse_name, warehouse_latitude, warehouse_longitude = warehouse_record #

            # Changed longitude to logitude in INSERT and RETURNING clauses for droneassignment table
            cur.execute("""
                INSERT INTO droneassignment (drone_id, drone_name, name, latitude, longitude, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, drone_id, drone_name, name, latitude, longitude, status
            """, (selected_drone_pk, drone_name, warehouse_name, warehouse_latitude, warehouse_longitude, status)) #
            new_assignment_record = cur.fetchone() #
            conn.commit() #

            new_assignment = {
                'id': new_assignment_record[0], #
                'drone_id': new_assignment_record[1], #
                'drone_name': new_assignment_record[2], #
                'warehouse_name': new_assignment_record[3], #
                'latitude': new_assignment_record[4], #
                'longitude': new_assignment_record[5], # new_assignment_record[5] gets value from returned logitude #
                'status': new_assignment_record[6] #
            }
            return jsonify({
                "message": f"Successfully assigned drone {drone_name} to warehouse {warehouse_name} with status {status}.", #
                "category": "success", #
                "assignment": new_assignment #
            }), 201 #

    except psycopg2.Error as e:
        print(f"Error assigning drone: {e}")
        if conn: conn.rollback() #
        return jsonify({"message": f"Database error assigning drone: {e}", "category": "error"}), 500 #
    except ValueError: # Catches errors from int(selected_warehouse_pk) #
        if conn: conn.rollback() #
        return jsonify({"message": f"Error: Invalid warehouse ID format '{selected_warehouse_pk}'.", "category": "error"}), 400 #
    finally:
        if conn:
            conn.close()

# API Endpoint to update an assignment's status
@app.route('/api/update_assignment_status/<int:assignment_id>', methods=['POST'])
def api_update_assignment_status(assignment_id):
    data = request.get_json() #
    new_status = data.get('status') #

    if not new_status or new_status not in ['Active', 'Inactive']: #
        return jsonify({"message": "Error: Valid status ('Active' or 'Inactive') is required.", "category": "warning"}), 400 #

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error: Could not connect to the database for status update.", "category": "error"}), 500 #

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM droneassignment WHERE id = %s", (assignment_id,)) #
            record_exists = cur.fetchone() #
            if not record_exists:
                 return jsonify({"message": f"Error: Assignment with ID {assignment_id} not found.", "category": "error"}), 404 #

            # Changed longitude to logitude in the RETURNING clause
            cur.execute("""
                UPDATE droneassignment
                SET status = %s
                WHERE id = %s
                RETURNING id, drone_id, drone_name, name, latitude, longitude, status
            """, (new_status, assignment_id)) #
            updated_assignment_record = cur.fetchone() #
            conn.commit() #

            if updated_assignment_record:
                updated_assignment = {
                    'id': updated_assignment_record[0], #
                    'drone_id': updated_assignment_record[1], #
                    'drone_name': updated_assignment_record[2], #
                    'warehouse_name': updated_assignment_record[3], #
                    'latitude': updated_assignment_record[4], #
                    'longitude': updated_assignment_record[5], # updated_assignment_record[5] gets value from returned logitude #
                    'status': updated_assignment_record[6] #
                }
                return jsonify({
                    "message": f"Assignment {assignment_id} status updated to {new_status}.", #
                    "category": "success", #
                    "assignment": updated_assignment #
                }), 200 #
            else: # Should not happen if record_exists check passes and update is successful #
                return jsonify({"message": f"Error: Assignment with ID {assignment_id} found but failed to update.", "category": "error"}), 500 #

    except psycopg2.Error as e:
        print(f"Error updating assignment status: {e}")
        if conn: conn.rollback() #
        return jsonify({"message": f"Database error updating status: {e}", "category": "error"}), 500 #
    finally:
        if conn:
            conn.close()


# API Endpoint to delete an assignment
@app.route('/api/delete_assignment/<int:assignment_id>', methods=['POST'])
def api_delete_assignment(assignment_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error: Could not connect to the database for deletion.", "category": "error"}), 500 #

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM droneassignment WHERE id = %s", (assignment_id,)) #
            record_exists = cur.fetchone() #
            if not record_exists:
                 return jsonify({"message": f"Error: Assignment with ID {assignment_id} not found.", "category": "error"}), 404 #

            cur.execute("DELETE FROM droneassignment WHERE id = %s", (assignment_id,)) #
            conn.commit() #

            if cur.rowcount > 0: #
                return jsonify({"message": "Assignment deleted successfully.", "category": "success", "deleted_id": assignment_id}), 200 #
            else:
                return jsonify({"message": f"Error: Assignment with ID {assignment_id} found but not deleted, or already deleted.", "category": "error"}), 404 #

    except psycopg2.Error as e:
        print(f"Error deleting assignment: {e}")
        if conn: conn.rollback() #
        return jsonify({"message": f"Database error deleting assignment: {e}", "category": "error"}), 500 #
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5008, debug=True) #