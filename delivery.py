import os
import psycopg2
from flask import Flask, request, jsonify
import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Database connection details
DB_HOST = "dpg-d0op2vuuk2gs738trhhg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_3wh9"
DB_USER = "shadowfly_3wh9_user"
DB_PASS = "4eX3uM5s2uX0wry7PFVG5YnqKOHUXFmF" # Consider using environment variables for passwords
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

# NEW: Endpoint for delivery missions
@app.route('/api/delivery_missions/<string:warehouse_name>', methods=['GET'])
def get_delivery_missions(warehouse_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # First, get packages with all required data present
        cur.execute("""
            SELECT 
                package_id,
                assigned_drone_id as drone_id,
                destination_lat,
                destination_lng,
                current_status
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
        
        for package_id, drone_id, dest_lat, dest_lng, status in packages:
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
