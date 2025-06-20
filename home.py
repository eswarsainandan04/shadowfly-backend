import psycopg2
import psycopg2.extras
import os
import logging
import hashlib
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_HOST = "dpg-d1aovm6uk2gs7390cttg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_um2n"
DB_USER = "shadowfly_um2n_user"
DB_PASS = "6ab9pofT8Tv0H5TqLWiD0qJZ0fTR8aNk"
DB_PORT = 5432

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return connection
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        return None

def execute_query(query, params=None, fetch_all=True):
    """Execute a database query and return results"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, params)
        
        if fetch_all:
            result = cursor.fetchall()
        else:
            result = cursor.fetchone()
            
        connection.commit()
        return result
    except psycopg2.Error as e:
        logger.error(f"Query execution error: {e}")
        connection.rollback()
        return None
    finally:
        cursor.close()
        connection.close()

@app.route('/api/warehouses', methods=['GET'])
def get_warehouses():
    """Get all warehouses with their coordinates"""
    try:
        query = "SELECT name, latitude, longitude FROM warehouses"
        warehouses = execute_query(query)
        
        if warehouses is None:
            return jsonify({'error': 'Failed to fetch warehouses'}), 500
        
        # Convert to list of dictionaries for JSON serialization
        warehouses_list = []
        for warehouse in warehouses:
            warehouses_list.append({
                'name': warehouse['name'],
                'latitude': float(warehouse['latitude']),
                'longitude': float(warehouse['longitude'])
            })
        
        logger.info(f"Retrieved {len(warehouses_list)} warehouses")
        return jsonify(warehouses_list)
    
    except Exception as e:
        logger.error(f"Error in get_warehouses: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/ddts', methods=['GET'])
def get_ddts():
    """Get all DDTs (Drone Delivery Terminals) with their coordinates"""
    try:
        query = "SELECT name, latitude, longitude FROM ddts"
        ddts = execute_query(query)
        
        if ddts is None:
            return jsonify({'error': 'Failed to fetch DDTs'}), 500
        
        # Convert to list of dictionaries for JSON serialization
        ddts_list = []
        for ddt in ddts:
            ddts_list.append({
                'name': ddt['name'],
                'latitude': float(ddt['latitude']),
                'longitude': float(ddt['longitude'])
            })
        
        logger.info(f"Retrieved {len(ddts_list)} DDTs")
        return jsonify(ddts_list)
    
    except Exception as e:
        logger.error(f"Error in get_ddts: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/network-status', methods=['GET'])
def get_network_status():
    """Get overall network status including counts and statistics"""
    try:
        warehouse_query = "SELECT COUNT(*) as count FROM warehouses"
        ddt_query = "SELECT COUNT(*) as count FROM ddts"
        
        warehouse_count = execute_query(warehouse_query, fetch_all=False)
        ddt_count = execute_query(ddt_query, fetch_all=False)
        
        if warehouse_count is None or ddt_count is None:
            return jsonify({'error': 'Failed to fetch network status'}), 500
        
        status = {
            'warehouses': {
                'count': warehouse_count['count'],
                'status': 'operational'
            },
            'ddts': {
                'count': ddt_count['count'],
                'status': 'operational'
            },
            'network_health': 'excellent',
            'last_updated': '2024-01-27T18:45:14Z'
        }
        
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"Error in get_network_status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        connection = get_db_connection()
        if connection:
            connection.close()
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'timestamp': '2024-01-27T18:45:14Z'
            })
        else:
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'timestamp': '2024-01-27T18:45:14Z'
            }), 503
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': '2024-01-27T18:45:14Z'
        }), 503

@app.route('/api/locations/search', methods=['GET'])
def search_locations():
    """Search for warehouses and DDTs by name or location"""
    try:
        search_term = request.args.get('q', '').strip()
        
        if not search_term:
            return jsonify({'error': 'Search term is required'}), 400
        
        # Search warehouses
        warehouse_query = """
            SELECT 'warehouse' as type, name, latitude, longitude 
            FROM warehouses 
            WHERE LOWER(name) LIKE LOWER(%s)
        """
        
        # Search DDTs
        ddt_query = """
            SELECT 'ddt' as type, name, latitude, longitude 
            FROM ddts 
            WHERE LOWER(name) LIKE LOWER(%s)
        """
        
        search_pattern = f"%{search_term}%"
        
        warehouses = execute_query(warehouse_query, (search_pattern,))
        ddts = execute_query(ddt_query, (search_pattern,))
        
        results = []
        
        if warehouses:
            for warehouse in warehouses:
                results.append({
                    'type': warehouse['type'],
                    'name': warehouse['name'],
                    'latitude': float(warehouse['latitude']),
                    'longitude': float(warehouse['longitude'])
                })
        
        if ddts:
            for ddt in ddts:
                results.append({
                    'type': ddt['type'],
                    'name': ddt['name'],
                    'latitude': float(ddt['latitude']),
                    'longitude': float(ddt['longitude'])
                })
        
        return jsonify({
            'query': search_term,
            'results': results,
            'count': len(results)
        })
    
    except Exception as e:
        logger.error(f"Error in search_locations: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    logger.info("Starting ShadowFly Drone Delivery API server...")
    logger.info(f"Database: {DB_NAME} on {DB_HOST}:{DB_PORT}")
    
    # Test database connection on startup
    connection = get_db_connection()
    if connection:
        logger.info("Database connection successful")
        connection.close()
    else:
        logger.error("Failed to connect to database")
    
    app.run(host='0.0.0.0', port=5080, debug=True)