import os
import psycopg2
import psycopg2.extras  # Required for dictionary cursor
from flask import Flask, request, jsonify
from flask_cors import CORS
# datetime was imported but not used in the original snippet.
# render_template was imported but not used in the original snippet.

app = Flask(__name__)
# Allowing all origins. For production, you might want to restrict this.
CORS(app) 

DB_HOST = "dpg-d0skka6mcj7s73f3q86g-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_nq0m"
DB_USER = "shadowfly_nq0m_user"
DB_PASS = "vwnAIGWvfqTUxHZsJAXsoA8HAJNiTWo5"
DB_PORT = 5432

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    return conn



@app.route('/get_drone_assignments_by_warehouse_name/<warehouse_name>', methods=['GET'])
def get_drone_assignments_by_warehouse_name(warehouse_name):
    conn = None
    try:
        conn = get_db_connection()
        # Using DictCursor to get results as dictionaries
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # SQL Query:
        # This query assumes that the 'name' column in the 'droneassignment' table
        # is intended to store the warehouse name by which you are filtering.
        # If 'name' refers to something else (e.g., the assignment's own name/ID),
        # and a different column stores the warehouse identifier, you'll need to adjust the WHERE clause.
        query = """
            SELECT name, latitude, longitude, drone_id, drone_name, status 
            FROM droneassignment 
            WHERE name = %s;
        """
        cur.execute(query, (warehouse_name,))
        assignments = cur.fetchall()
        
        # Convert list of psycopg2.extras.DictRow objects to a list of standard dictionaries
        assignments_list = [dict(row) for row in assignments]
        
        cur.close()  # Good practice to close the cursor
        return jsonify(assignments_list), 200

    except psycopg2.Error as db_err:
        # Log PostgreSQL specific errors
        app.logger.error(f"Database error fetching drone assignments for warehouse '{warehouse_name}': {db_err}")
        # Provide a more generic error to the client, but log the details
        return jsonify({"error": "A database error occurred while fetching drone assignments.", "details": str(db_err)}), 500
    except Exception as e:
        # Log any other unexpected errors
        app.logger.error(f"Unexpected error fetching drone assignments for warehouse '{warehouse_name}': {e}")
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500
    finally:
        if conn:
            conn.close() # Ensure the connection is always closed

@app.route('/get_packages_by_warehouse_name/<warehouse_name>', methods=['GET'])
def get_packages_by_warehouse_name(warehouse_name):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # SQL Query:
        # This query assumes 'warehouse_name' column exists in 'packagemanagement' table.
        query = """
            SELECT package_id, last_update_time
            FROM packagemanagement 
            WHERE warehouse_name = %s;
        """
        cur.execute(query, (warehouse_name,))
        packages = cur.fetchall()
        
        packages_list = [dict(row) for row in packages]
        cur.close()
        return jsonify(packages_list), 200

    except psycopg2.Error as db_err:
        app.logger.error(f"Database error fetching packages for warehouse '{warehouse_name}': {db_err}")
        return jsonify({"error": "A database error occurred while fetching packages.", "details": str(db_err)}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching packages for warehouse '{warehouse_name}': {e}")
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':

    app.run(debug=True, port=5000)