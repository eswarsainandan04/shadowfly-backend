import os
import psycopg2
from flask import Flask, request, jsonify
import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Database connection details
DB_HOST = "dpg-d1aovm6uk2gs7390cttg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_um2n"
DB_USER = "shadowfly_um2n_user"
DB_PASS = "6ab9pofT8Tv0H5TqLWiD0qJZ0fTR8aNk"
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
        
        # Get user role from users_data table
        cur.execute("SELECT role FROM users_data WHERE username = %s;", (username,))
        role_result = cur.fetchone()
        
        if role_result:
            return jsonify({
                "role": role_result[0].lower(),
                "assigned_location": None,
                "location_type": None
            })
        else:
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

@app.route('/api/warehouse_search', methods=['GET'])
def search_warehouses():
    """Endpoint to search warehouses by name"""
    conn = None
    cur = None
    try:
        search_term = request.args.get('q', '')
        conn = get_db_connection()
        cur = conn.cursor()
        
        if search_term:
            cur.execute("""
                SELECT name, latitude, longitude 
                FROM warehouses 
                WHERE name ILIKE %s 
                ORDER BY name;
            """, (f'%{search_term}%',))
        else:
            cur.execute("SELECT name, latitude, longitude FROM warehouses ORDER BY name;")
        
        warehouses = cur.fetchall()
        
        # Format the data for the dropdown
        formatted_warehouses = []
        for name, latitude, longitude in warehouses:
            formatted_warehouses.append({
                "label": f"{name} ({latitude},{longitude})",
                "value": name,
                "latitude": latitude,
                "longitude": longitude
            })
        
        return jsonify(formatted_warehouses)
    except Exception as e:
        print(f"Error searching warehouses: {e}")
        return jsonify({"error": "Failed to search warehouses"}), 500
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
        cur.execute("SELECT name, latitude, longitude FROM warehouses ORDER BY name;")
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
                pm.package_id,
                pm.tracking_code,
                pm.sender_id,
                pm.customer_id,
                pm.warehouse_name,
                pm.destination_address,
                pm.destination_lat,
                pm.destination_lng,
                pm.current_status,
                pm.weight_kg,
                pm.assigned_drone_id,
                pm.estimated_arrival_time,
                pm.dispatch_time,
                pm.delivery_time,
                pm.last_known_lat,
                pm.last_known_lng,
                pm.last_update_time,
                pm.item_details
            FROM packagemanagement pm
            WHERE pm.package_id = %s;
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

@app.route('/api/package_monitor/<string:package_id>', methods=['GET'])
def get_package_monitor_data(package_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get complete package data along with destination name
        cur.execute("""
            SELECT 
                pm.package_id,
                pm.tracking_code,
                pm.sender_id,
                pm.customer_id,
                pm.warehouse_name,
                pm.destination_address,
                pm.destination_lat,
                pm.destination_lng,
                pm.current_status,
                pm.weight_kg,
                pm.assigned_drone_id,
                pm.estimated_arrival_time,
                pm.dispatch_time,
                pm.delivery_time,
                pm.last_known_lat,
                pm.last_known_lng,
                pm.last_update_time,
                pm.item_details,
                ddts.name as destination_name
            FROM packagemanagement pm
            LEFT JOIN ddts ON pm.destination_lat = ddts.latitude AND pm.destination_lng = ddts.longitude
            WHERE pm.package_id = %s;
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
            "destination_name": package_row[18] if package_row[18] else "Delivery Location", # Use actual name if available
            "warehouse_lat": warehouse_coords[0] if warehouse_coords else None,
            "warehouse_lng": warehouse_coords[1] if warehouse_coords else None,
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

@app.route('/api/available_packages/<string:warehouse_name>', methods=['GET'])
def get_available_packages(warehouse_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
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

@app.route('/api/delivery_missions/<string:warehouse_name>', methods=['GET'])
def get_delivery_missions(warehouse_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get packages with all required data present, and destination name
        cur.execute("""
            SELECT 
                pm.package_id,
                pm.tracking_code,
                pm.sender_id,
                pm.customer_id,
                pm.warehouse_name,
                pm.destination_address,
                pm.destination_lat,
                pm.destination_lng,
                pm.current_status,
                pm.weight_kg,
                pm.assigned_drone_id,
                pm.estimated_arrival_time,
                pm.dispatch_time,
                pm.delivery_time,
                pm.last_known_lat,
                pm.last_known_lng,
                pm.last_update_time,
                pm.item_details,
                ddts.name as destination_name
            FROM packagemanagement pm
            LEFT JOIN ddts ON pm.destination_lat = ddts.latitude AND pm.destination_lng = ddts.longitude
            WHERE pm.current_status IN ('Pending', 'Dispatched', 'In Transit', 'Out for Delivery')
            AND pm.warehouse_name = %s
            AND pm.package_id IS NOT NULL 
            AND pm.assigned_drone_id IS NOT NULL 
            AND pm.destination_lat IS NOT NULL 
            AND pm.destination_lng IS NOT NULL 
            AND pm.current_status IS NOT NULL;
        """, (warehouse_name,))
        
        packages = cur.fetchall()
        
        if not packages:
            return jsonify([])
        
        formatted_missions = []
        
        for row in packages:
            package_id, tracking_code, sender_id, customer_id, warehouse_name, destination_address, dest_lat, dest_lng, status, weight_kg, drone_id, estimated_arrival, dispatch_time, delivery_time, last_lat, last_lng, last_update, item_details, destination_name = row
            
            # Format destination for display as "name(latitude,longitude)"
            destination_display = f"{destination_name or destination_address}({dest_lat}, {dest_lng})"
            
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
                "destination": destination_display, # This will be used in DeliveryPage.js
                "status": status,
                "destination_name": destination_name # This will be used in Monitor.js
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

if __name__ == '__main__':
    app.run(debug=True, port=5042)