import os
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import datetime
import uuid
import logging

app = Flask(__name__)
CORS(app)

DB_HOST = "dpg-d1aovm6uk2gs7390cttg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_um2n"
DB_USER = "shadowfly_um2n_user"
DB_PASS = "6ab9pofT8Tv0H5TqLWiD0qJZ0fTR8aNk"
DB_PORT = 5432

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None
    
    
get_db_connection()

@app.route('/api/packages', methods=['GET'])
def get_packages():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        status_filter = request.args.get('status')
        if status_filter:
            cursor.execute("""
                SELECT * FROM packagemanagement 
                WHERE current_status = %s 
                ORDER BY last_update_time DESC
            """, (status_filter,))
        else:
            cursor.execute("""
                SELECT * FROM packagemanagement 
                ORDER BY last_update_time DESC
            """)
        
        packages = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify(packages)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delivery-drones', methods=['GET'])
def get_delivery_drones():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get distinct assigned drone IDs from packagemanagement and join with dronesdata
        cursor.execute("""
            SELECT DISTINCT dd.*
            FROM dronesdata dd
            INNER JOIN (
                SELECT DISTINCT assigned_drone_id 
                FROM packagemanagement 
                WHERE assigned_drone_id IS NOT NULL
            ) pm ON dd.drone_id = pm.assigned_drone_id
        """)
        
        drones = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify(drones)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/drone/<drone_id>', methods=['GET'])
def get_drone_data(drone_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM dronesdata WHERE drone_id = %s", (drone_id,))
        
        drone = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if drone:
            return jsonify(drone)
        else:
            return jsonify({"error": "Drone not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/drone-destination/<drone_id>', methods=['GET'])
def get_drone_destination(drone_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get destination coordinates from packagemanagement
        cursor.execute("""
            SELECT destination_lat, destination_lng, warehouse_name
            FROM packagemanagement
            WHERE assigned_drone_id = %s
            LIMIT 1
        """, (drone_id,))
        
        destination = cursor.fetchone()
        
        if not destination:
            cursor.close()
            conn.close()
            return jsonify({"error": "No destination found for this drone"}), 404
        
        # Get DDT information based on destination coordinates
        if destination['destination_lat'] and destination['destination_lng']:
            cursor.execute("""
                SELECT *
                FROM ddts
                WHERE latitude = %s AND longitude = %s
            """, (destination['destination_lat'], destination['destination_lng']))
            
            ddts = cursor.fetchall()
            
            # Process DDT data
            for ddt in ddts:
                available_racks = []
                total_racks = ddt['total_racks'] or 0
                
                if total_racks > 0:
                    for i in range(1, total_racks + 1):
                        rack_column = f"rack_{i:02d}"
                        if rack_column in ddt and ddt[rack_column] is None:  # NULL means available
                            available_racks.append({
                                'rack_number': i,
                                'rack_name': f"Rack {i:02d}",
                                'rack_column': rack_column
                            })
                
                ddt['available_racks'] = available_racks
                ddt['available_count'] = len(available_racks)
            
            destination['ddts'] = ddts
        else:
            destination['ddts'] = []
        
        # Get warehouse coordinates if available
        if destination['warehouse_name']:
            cursor.execute("""
                SELECT latitude, longitude
                FROM warehouses
                WHERE name = %s
            """, (destination['warehouse_name'],))
            
            warehouse = cursor.fetchone()
            if warehouse:
                destination['warehouse_coords'] = warehouse
        
        cursor.close()
        conn.close()
        
        return jsonify(destination)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ddts', methods=['GET'])
def get_ddts():
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Find DDTs with exact coordinate match
        cursor.execute("""
            SELECT * FROM ddts 
            WHERE latitude = %s AND longitude = %s
        """, (lat, lng))
        
        ddts = cursor.fetchall()
        
        # For each DDT, get available racks (NULL values)
        for ddt in ddts:
            available_racks = []
            total_racks = ddt['total_racks'] or 0
            
            if total_racks > 0:
                for i in range(1, total_racks + 1):
                    rack_column = f"rack_{i:02d}"
                    if rack_column in ddt and ddt[rack_column] is None:  # NULL means available
                        available_racks.append({
                            'rack_number': i,
                            'rack_name': f"Rack {i:02d}",
                            'rack_column': rack_column
                        })
            
            ddt['available_racks'] = available_racks
            ddt['available_count'] = len(available_racks)
        
        cursor.close()
        conn.close()
        
        return jsonify(ddts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delivery/launch', methods=['POST'])
def launch_delivery():
    try:
        data = request.json
        package_id = data.get('package_id')
        delivery_method = data.get('delivery_method')  # 'DDT' or 'Winch'
        selected_rack = data.get('selected_rack')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        
        # Update package status to 'Out for Delivery'
        cursor.execute("""
            UPDATE packagemanagement 
            SET current_status = 'Out for Delivery',
                dispatch_time = %s,
                last_update_time = %s
            WHERE package_id = %s
        """, (datetime.datetime.now(), datetime.datetime.now(), package_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"Delivery launched via {delivery_method}",
            "package_id": package_id,
            "delivery_method": delivery_method,
            "selected_rack": selected_rack
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delivery/abort', methods=['POST'])
def abort_delivery():
    try:
        data = request.json
        package_id = data.get('package_id')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        
        # Update package status back to 'Pending'
        cursor.execute("""
            UPDATE packagemanagement 
            SET current_status = 'Pending',
                last_update_time = %s
            WHERE package_id = %s
        """, (datetime.datetime.now(), package_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Delivery aborted",
            "package_id": package_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delivery/land', methods=['POST'])
def land_drone():
    try:
        data = request.json
        package_id = data.get('package_id')
        
        return jsonify({
            "status": "success",
            "message": "Drone landing in safety zone",
            "package_id": package_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delivery/stop', methods=['POST'])
def stop_drone():
    try:
        data = request.json
        package_id = data.get('package_id')
        
        return jsonify({
            "status": "success",
            "message": "Drone stopped",
            "package_id": package_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delivery/rtl', methods=['POST'])
def return_to_launch():
    try:
        data = request.json
        package_id = data.get('package_id')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        
        # Update package status back to 'Pending'
        cursor.execute("""
            UPDATE packagemanagement 
            SET current_status = 'Pending',
                last_update_time = %s
            WHERE package_id = %s
        """, (datetime.datetime.now(), package_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Drone returning to launch",
            "package_id": package_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reserve-rack', methods=['POST'])
def reserve_rack():
    try:
        data = request.json
        ddt_id = data.get('ddt_id')
        rack_column = data.get('rack_column')
        package_id = data.get('package_id')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        
        # Reserve the rack by updating it with package_id
        query = f"UPDATE ddts SET {rack_column} = %s WHERE id = %s AND {rack_column} IS NULL"
        cursor.execute(query, (package_id, ddt_id))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Rack is no longer available"}), 400
        
        # Update available_racks count
        cursor.execute("UPDATE ddts SET avialable_racks = avialable_racks - 1 WHERE id = %s", (ddt_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "message": "Rack reserved successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/warehouse/<warehouse_name>', methods=['GET'])
def get_warehouse_coordinates(warehouse_name):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT latitude, longitude FROM warehouses WHERE name = %s", (warehouse_name,))
        
        warehouse = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if warehouse:
            return jsonify(warehouse)
        else:
            return jsonify({"error": "Warehouse not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5090)
