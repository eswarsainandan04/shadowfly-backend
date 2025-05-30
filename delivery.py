import os
import psycopg2
from flask import Flask, request, jsonify
import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

DB_HOST = "dpg-d0skka6mcj7s73f3q86g-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_nq0m"
DB_USER = "shadowfly_nq0m_user"
DB_PASS = "vwnAIGWvfqTUxHZsJAXsoA8HAJNiTWo5"
DB_PORT = 5432

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    return conn

@app.route('/api/user_role/<string:username>', methods=['GET'])
def get_user_role(username):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check assigned_warehouse first
        cur.execute("SELECT assigned_warehouse FROM users_data WHERE username = %s;", (username,))
        warehouse_result = cur.fetchone()
        
        if warehouse_result and warehouse_result[0] is not None:
            return jsonify({
                "role": "warehouse",
                "assigned_location": warehouse_result[0],
                "location_type": "warehouse"
            })
        
        # If no warehouse, check assigned_ddt
        cur.execute("SELECT assigned_ddt FROM users_data WHERE username = %s;", (username,))
        ddt_result = cur.fetchone()
        
        if ddt_result and ddt_result[0] is not None:
            return jsonify({
                "role": "ddt",
                "assigned_location": ddt_result[0],
                "location_type": "ddt"
            })
        
        # If neither assigned
        return jsonify({
            "role": "none",
            "assigned_location": None,
            "location_type": None
        })
        
    except Exception as e:
        print(f"Error fetching user role: {e}")
        return jsonify({"error": "Failed to fetch user role"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/ddt_details/<string:ddt_name>', methods=['GET'])
def get_ddt_details(ddt_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get DDT details
        cur.execute("""
            SELECT 
                name, 
                latitude, 
                longitude,
                status
            FROM ddts
            WHERE name = %s;
        """, (ddt_name,))
        
        ddt_row = cur.fetchone()
        
        if not ddt_row:
            return jsonify({"error": "DDT not found"}), 404

        ddt_info = {
            "name": ddt_row[0],
            "latitude": ddt_row[1],
            "longitude": ddt_row[2],
            "status": ddt_row[3]
        }
            
        return jsonify(ddt_info)
    except Exception as e:
        print(f"Error fetching DDT details: {e}")
        return jsonify({"error": "Failed to fetch DDT details"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/drone_assignments', methods=['GET'])
def get_drone_assignments():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, latitude, longitude FROM warehouses;")
        drone_assignments = cur.fetchall()
        
        # Format the data for the dropdown
        formatted_assignments = []
        for name, latitude, longitude in drone_assignments:
            formatted_assignments.append({
                "label": f"{name} ({latitude},{longitude})",
                "value": name, # The value to use when selected
                "latitude": latitude,
                "longitude": longitude
            })
        
        return jsonify(formatted_assignments)
    except Exception as e:
        print(f"Error fetching drone assignments: {e}")
        return jsonify({"error": "Failed to fetch drone assignments"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/warehouse_details/<string:warehouse_name>', methods=['GET'])
def get_warehouse_details(warehouse_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get warehouse details
        cur.execute("""
            SELECT 
                name, 
                latitude, 
                longitude
            FROM warehouses
            WHERE name = %s;
        """, (warehouse_name,))
        
        warehouse_row = cur.fetchone()
        
        if not warehouse_row:
            return jsonify({"error": "Warehouse not found"}), 404

        warehouse_info = {
            "name": warehouse_row[0],
            "latitude": warehouse_row[1],
            "longitude": warehouse_row[2],
            "drones": []
        }

        # Get associated drones for the warehouse
        cur.execute("""
            SELECT 
                drone_id, 
                drone_name, 
                status
            FROM droneassignment
            WHERE name = %s;
        """, (warehouse_name,))
        
        drone_rows = cur.fetchall()
        
        for row in drone_rows:
            warehouse_info["drones"].append({
                "drone_id": row[0],
                "drone_name": row[1],
                "status": row[2]
            })
            
        return jsonify(warehouse_info)
    except Exception as e:
        print(f"Error fetching warehouse details: {e}")
        return jsonify({"error": "Failed to fetch warehouse details"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            
@app.route('/api/package/<string:package_id>', methods=['GET'])
def get_package_details(package_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Fetch all columns for the given package_id
        cur.execute("""
            SELECT 
                package_id,
                tracking_code,
                sender_id,
                customer_id,
                warehouse_name,
                destination_address,
                destination_lat,
                destination_lng,
                current_status,
                weight_kg,
                assigned_drone_id,
                estimated_arrival_time,
                dispatch_time,
                delivery_time,
                last_known_lat,
                last_known_lng,
                last_update_time,
                item_details
            FROM packagemanagement
            WHERE package_id = %s;
        """, (package_id,))
        
        row = cur.fetchone()
        
        if not row:
            return jsonify({"error": "Package not found"}), 404
        
        columns = [
            "package_id", "tracking_code", "sender_id", "customer_id", "warehouse_name",
            "destination_address", "destination_lat", "destination_lng", "current_status",
            "weight_kg", "assigned_drone_id", "estimated_arrival_time", "dispatch_time",
            "delivery_time", "last_known_lat", "last_known_lng", "last_update_time",
            "item_details"
        ]
        
        package_details = dict(zip(columns, row))
        
        return jsonify(package_details)
    
    except Exception as e:
        print(f"Error fetching package details: {e}")
        return jsonify({"error": "Failed to fetch package details"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# NEW: Enhanced endpoint to get complete package data for monitoring
@app.route('/api/package_monitor/<string:package_id>', methods=['GET'])
def get_package_monitor_data(package_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get complete package data
        cur.execute("""
            SELECT 
                package_id,
                tracking_code,
                sender_id,
                customer_id,
                warehouse_name,
                destination_address,
                destination_lat,
                destination_lng,
                current_status,
                weight_kg,
                assigned_drone_id,
                estimated_arrival_time,
                dispatch_time,
                delivery_time,
                last_known_lat,
                last_known_lng,
                last_update_time,
                item_details
            FROM packagemanagement
            WHERE package_id = %s;
        """, (package_id,))
        
        package_row = cur.fetchone()
        
        if not package_row:
            return jsonify({"error": "Package not found"}), 404
        
        # Get warehouse coordinates
        cur.execute("""
            SELECT latitude, longitude 
            FROM warehouses 
            WHERE name = %s;
        """, (package_row[4],))  # warehouse_name
        
        warehouse_coords = cur.fetchone()
        
        # Get destination name
        destination_name = None
        if package_row[6] and package_row[7]:  # destination_lat, destination_lng
            cur.execute("""
                SELECT name 
                FROM ddts 
                WHERE latitude = %s AND longitude = %s;
            """, (package_row[6], package_row[7]))
            
            dest_row = cur.fetchone()
            if dest_row:
                destination_name = dest_row[0]
        
        # Format response
        package_data = {
            "package_id": package_row[0],
            "tracking_code": package_row[1],
            "sender_id": package_row[2],
            "customer_id": package_row[3],
            "warehouse_name": package_row[4],
            "destination_address": package_row[5],
            "destination_lat": package_row[6],
            "destination_lng": package_row[7],
            "current_status": package_row[8],
            "weight_kg": package_row[9],
            "assigned_drone_id": package_row[10],
            "estimated_arrival_time": package_row[11],
            "dispatch_time": package_row[12],
            "delivery_time": package_row[13],
            "last_known_lat": package_row[14],
            "last_known_lng": package_row[15],
            "last_update_time": package_row[16],
            "item_details": package_row[17],
            "warehouse_lat": warehouse_coords[0] if warehouse_coords else None,
            "warehouse_lng": warehouse_coords[1] if warehouse_coords else None,
            "destination_name": destination_name
        }
        
        return jsonify(package_data)
        
    except Exception as e:
        print(f"Error fetching package monitor data: {e}")
        return jsonify({"error": "Failed to fetch package monitor data"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# MODIFIED: Endpoint for available packages to filter by warehouse_name
@app.route('/api/available_packages/<string:warehouse_name>', methods=['GET'])
def get_available_packages(warehouse_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Ensure 'packagemanagement' table has a 'warehouse_name' column
        # or a way to link packages to warehouses (e.g., through droneassignment)
        cur.execute("SELECT package_id, item_details FROM packagemanagement WHERE warehouse_name = %s;", (warehouse_name,))
        packages = cur.fetchall()
        
        formatted_packages = []
        for package_id, item_details in packages:
            formatted_packages.append({
                "package_id": package_id,
                "item_details": item_details
            })
        
        return jsonify(formatted_packages)
    except Exception as e:
        print(f"Error fetching available packages for warehouse {warehouse_name}: {e}")
        return jsonify({"error": "Failed to fetch available packages"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# MODIFIED: Enhanced delivery missions endpoint with complete package data
@app.route('/api/delivery_missions/<string:warehouse_name>', methods=['GET'])
def get_delivery_missions(warehouse_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get packages with all required data present
        cur.execute("""
            SELECT 
                package_id,
                tracking_code,
                sender_id,
                customer_id,
                warehouse_name,
                destination_address,
                destination_lat,
                destination_lng,
                current_status,
                weight_kg,
                assigned_drone_id,
                estimated_arrival_time,
                dispatch_time,
                delivery_time,
                last_known_lat,
                last_known_lng,
                last_update_time,
                item_details
            FROM packagemanagement 
            WHERE current_status IN ('Pending', 'Dispatched', 'In Transit', 'Out for Delivery')
            AND warehouse_name = %s
            AND package_id IS NOT NULL 
            AND assigned_drone_id IS NOT NULL 
            AND destination_lat IS NOT NULL 
            AND destination_lng IS NOT NULL 
            AND current_status IS NOT NULL;
        """, (warehouse_name,))
        
        packages = cur.fetchall()
        
        if not packages:
            return jsonify([])
        
        formatted_missions = []
        
        for row in packages:
            package_id, tracking_code, sender_id, customer_id, warehouse_name, destination_address, dest_lat, dest_lng, status, weight_kg, drone_id, estimated_arrival, dispatch_time, delivery_time, last_lat, last_lng, last_update, item_details = row
            
            # Get destination name from ddts table
            cur.execute("""
                SELECT name 
                FROM ddts 
                WHERE latitude = %s AND longitude = %s;
            """, (dest_lat, dest_lng))
            
            destination_row = cur.fetchone()
            
            if destination_row:
                destination_name = destination_row[0]
                destination_display = f"{destination_name} ({dest_lat}, {dest_lng})"
            else:
                destination_display = f"Unknown Location ({dest_lat}, {dest_lng})"
            
            formatted_missions.append({
                "package_id": package_id,
                "tracking_code": tracking_code,
                "sender_id": sender_id,
                "customer_id": customer_id,
                "warehouse_name": warehouse_name,
                "destination_address": destination_address,
                "destination_lat": dest_lat,
                "destination_lng": dest_lng,
                "current_status": status,
                "weight_kg": weight_kg,
                "assigned_drone_id": drone_id,
                "estimated_arrival_time": estimated_arrival,
                "dispatch_time": dispatch_time,
                "delivery_time": delivery_time,
                "last_known_lat": last_lat,
                "last_known_lng": last_lng,
                "last_update_time": last_update,
                "item_details": item_details,
                "drone_id": drone_id,
                "destination": destination_display,
                "status": status
            })
        
        return jsonify(formatted_missions)
        
    except Exception as e:
        print(f"Error fetching delivery missions: {e}")
        return jsonify({"error": "Failed to fetch delivery missions"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# NEW: DDT delivery missions endpoint
@app.route('/api/ddt_delivery_missions/<string:ddt_name>', methods=['GET'])
def get_ddt_delivery_missions(ddt_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # First get DDT coordinates
        cur.execute("""
            SELECT latitude, longitude 
            FROM ddts 
            WHERE name = %s;
        """, (ddt_name,))
        
        ddt_coords = cur.fetchone()
        if not ddt_coords:
            return jsonify({"error": "DDT not found"}), 404
        
        ddt_lat, ddt_lng = ddt_coords
        
        # Get packages destined for this DDT
        cur.execute("""
            SELECT 
                package_id,
                tracking_code,
                sender_id,
                customer_id,
                warehouse_name,
                destination_address,
                destination_lat,
                destination_lng,
                current_status,
                weight_kg,
                assigned_drone_id,
                estimated_arrival_time,
                dispatch_time,
                delivery_time,
                last_known_lat,
                last_known_lng,
                last_update_time,
                item_details
            FROM packagemanagement 
            WHERE current_status IN ('Pending', 'Dispatched', 'In Transit', 'Out for Delivery')
            AND destination_lat = %s 
            AND destination_lng = %s
            AND package_id IS NOT NULL 
            AND assigned_drone_id IS NOT NULL 
            AND current_status IS NOT NULL;
        """, (ddt_lat, ddt_lng))
        
        packages = cur.fetchall()
        
        if not packages:
            return jsonify([])
        
        formatted_missions = []
        
        for row in packages:
            package_id, tracking_code, sender_id, customer_id, warehouse_name, destination_address, dest_lat, dest_lng, status, weight_kg, drone_id, estimated_arrival, dispatch_time, delivery_time, last_lat, last_lng, last_update, item_details = row
            
            formatted_missions.append({
                "package_id": package_id,
                "tracking_code": tracking_code,
                "sender_id": sender_id,
                "customer_id": customer_id,
                "warehouse_name": warehouse_name,
                "destination_address": destination_address,
                "destination_lat": dest_lat,
                "destination_lng": dest_lng,
                "current_status": status,
                "weight_kg": weight_kg,
                "assigned_drone_id": drone_id,
                "estimated_arrival_time": estimated_arrival,
                "dispatch_time": dispatch_time,
                "delivery_time": delivery_time,
                "last_known_lat": last_lat,
                "last_known_lng": last_lng,
                "last_update_time": last_update,
                "item_details": item_details,
                "drone_id": drone_id,
                "from": warehouse_name,
                "status": status
            })
        
        return jsonify(formatted_missions)
        
    except Exception as e:
        print(f"Error fetching DDT delivery missions: {e}")
        return jsonify({"error": "Failed to fetch DDT delivery missions"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            
            
@app.route('/api/update_package_status', methods=['POST'])
def update_package_status():
    conn = None
    cur = None
    try:
        data = request.json
        package_id = data.get('package_id')
        status = data.get('status')
        
        if not package_id or not status:
            return jsonify({"error": "Missing package_id or status"}), 400
            
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE packagemanagement 
            SET current_status = %s 
            WHERE package_id = %s
            RETURNING package_id;
        """, (status, package_id))
        
        updated = cur.fetchone()
        conn.commit()
        
        if not updated:
            return jsonify({"error": "Package not found or update failed"}), 404
            
        return jsonify({"success": True, "message": "Package status updated successfully"})
        
    except Exception as e:
        print(f"Error updating package status: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": "Failed to update package status"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            
            
            

if __name__ == '__main__':
    app.run(debug=True, port=5000)
