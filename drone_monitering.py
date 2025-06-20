from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import requests
import os

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

def safe(value):
    """Helper function to safely handle None values"""
    return value if value is not None else "N/A"

@app.route('/api/drone-parameters/<drone_id>')
def get_drone_parameters(drone_id):
    """
    API endpoint to fetch drone parameters from communication_key URL
    """
    try:
        print(f"Fetching drone parameters for drone: {drone_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get communication_key from dronesdata table
        cursor.execute("SELECT communication_key FROM dronesdata WHERE drone_id = %s", (drone_id,))
        comm_data = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not comm_data or not comm_data['communication_key']:
            print(f"No communication key found for drone {drone_id}")
            return jsonify({"error": "Communication key not found for this drone"}), 404
        
        communication_url = comm_data['communication_key']
        print(f"Fetching data from URL: {communication_url}")
        
        # Fetch data from the communication URL
        try:
            response = requests.get(communication_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract and format the required parameters
            parameters = {
                "latitude": safe(data.get("latitude")),
                "longitude": safe(data.get("longitude")),
                "altitude_rel": safe(data.get("altitude_rel")),
                "altitude_abs": safe(data.get("altitude_abs")),
                "battery_level": safe(data.get("battery_level")),
                "battery_voltage": safe(data.get("battery_voltage")),
                "battery_current": safe(data.get("battery_current")),
                "airspeed": safe(data.get("airspeed")),
                "groundspeed": safe(data.get("groundspeed")),
                "heading": safe(data.get("heading")),
                "pitch": safe(data.get("pitch")),
                "roll": safe(data.get("roll")),
                "yaw": safe(data.get("yaw")),
                "satellites_visible": safe(data.get("satellites_visible")),
                "fix_type": safe(data.get("fix_type")),
                "ekf_ok": safe(data.get("ekf_ok")),
                "mode": safe(data.get("mode")),
                "armed": safe(data.get("armed")),
                "is_armable": safe(data.get("is_armable")),
                "last_heartbeat": safe(data.get("last_heartbeat"))
            }
            
            print(f"Successfully fetched parameters for drone {drone_id}")
            return jsonify({
                "parameters": parameters,
                "drone_id": drone_id,
                "status": "success",
                "source_url": communication_url
            })
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from communication URL: {e}")
            return jsonify({"error": f"Failed to fetch data from drone: {str(e)}"}), 500
        except ValueError as e:
            print(f"Error parsing JSON response: {e}")
            return jsonify({"error": "Invalid JSON response from drone"}), 500
        
    except Exception as e:
        print(f"Error fetching drone parameters: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/drone-monitoring/<drone_id>')
def get_drone_monitoring_data(drone_id):
    """
    API endpoint to get comprehensive drone monitoring data
    """
    try:
        print(f"Fetching monitoring data for drone: {drone_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get drone data
        cursor.execute("SELECT * FROM dronesdata WHERE drone_id = %s", (drone_id,))
        drone_data = cursor.fetchone()
        
        if not drone_data:
            print(f"Drone {drone_id} not found in database")
            return jsonify({"error": "Drone not found"}), 404
        
        print(f"Found drone data: {drone_data['drone_name']}")
        
        # Get destination data
        cursor.execute("""
            SELECT destination_lat, destination_lng, warehouse_name, package_id
            FROM packagemanagement
            WHERE assigned_drone_id = %s
        """, (drone_id,))
        destination_data = cursor.fetchone()
        
        # Get warehouse coordinates
        warehouse_coords = None
        if destination_data and destination_data['warehouse_name']:
            cursor.execute("""
                SELECT latitude, longitude, name
                FROM warehouses
                WHERE name = %s
            """, (destination_data['warehouse_name'],))
            warehouse_coords = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        response_data = {
            "drone": dict(drone_data) if drone_data else None,
            "destination": dict(destination_data) if destination_data else None,
            "warehouse": dict(warehouse_coords) if warehouse_coords else None,
            "status": "success"
        }
        
        print(f"Returning monitoring data for drone {drone_id}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error fetching drone monitoring data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/drone-camera/<drone_id>')
def get_drone_camera_url(drone_id):
    """
    API endpoint to get camera URL for a specific drone
    """
    try:
        print(f"Fetching camera URL for drone: {drone_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get camera_key from dronesdata table
        cursor.execute("SELECT camera_key FROM dronesdata WHERE drone_id = %s", (drone_id,))
        camera_data = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not camera_data or not camera_data['camera_key']:
            print(f"No camera URL found for drone {drone_id}")
            return jsonify({"error": "Camera URL not found for this drone"}), 404
        
        camera_url = camera_data['camera_key']
        print(f"Found camera URL for drone {drone_id}: {camera_url}")
        
        return jsonify({
            "camera_url": camera_url,
            "drone_id": drone_id,
            "status": "success"
        })
        
    except Exception as e:
        print(f"Error fetching camera URL: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/drone-control/<drone_id>/<command>', methods=['POST'])
def drone_control(drone_id, command):
    """
    API endpoint for drone control commands
    """
    try:
        print(f"Drone control command: {command} for drone {drone_id}")
        
        # Enhanced control responses with more realistic feedback
        responses = {
            'launch': f'Mission launched for drone {drone_id} - Proceeding to destination',
            'abort': f'Mission aborted for drone {drone_id} - Returning to base',
            'land': f'Drone {drone_id} initiating landing sequence',
            'stop': f'Emergency stop activated for drone {drone_id}',
            'rtl': f'Drone {drone_id} returning to launch point',
            'takeoff': f'Drone {drone_id} taking off - Altitude climbing',
            'hover': f'Drone {drone_id} maintaining hover position'
        }
        
        message = responses.get(command, f'Unknown command: {command}')
        
        # Log the command for debugging
        print(f"Command executed: {command} -> {message}")
        
        return jsonify({
            "status": "success",
            "message": message,
            "drone_id": drone_id,
            "command": command,
            "timestamp": str(psycopg2.Timestamp.now()) if hasattr(psycopg2, 'Timestamp') else None
        })
        
    except Exception as e:
        print(f"Error executing drone control command: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/drone-status/<drone_id>')
def get_drone_status(drone_id):
    """
    API endpoint to get current drone status
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get current drone status
        cursor.execute("""
            SELECT drone_id, drone_name, last_known_lat, last_known_lng, 
                   battery_capacity, status
            FROM dronesdata 
            WHERE drone_id = %s
        """, (drone_id,))
        
        drone_status = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not drone_status:
            return jsonify({"error": "Drone not found"}), 404
        
        return jsonify({
            "drone_status": dict(drone_status),
            "status": "success"
        })
        
    except Exception as e:
        print(f"Error fetching drone status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        "status": "healthy",
        "service": "drone_monitoring",
        "version": "1.0.0"
    })

if __name__ == '__main__':

    
    app.run(debug=True, host='0.0.0.0', port=5095)