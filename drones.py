import os
import csv
import io
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_HOST = "dpg-d0skka6mcj7s73f3q86g-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_nq0m"
DB_USER = "shadowfly_nq0m_user"
DB_PASS = "vwnAIGWvfqTUxHZsJAXsoA8HAJNiTWo5"
DB_PORT = 5432

def get_db_connection():
    """Establishes a connection to the PostgreSQL database and ensures the table exists."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT
        )
        # Add the CREATE TABLE IF NOT EXISTS statement here
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dronesdata (
                    id SERIAL PRIMARY KEY,
                    drone_id character varying(225),
                    drone_name character varying(225),
                    model character varying(225),
                    drone_type character varying(225),
                    weight double precision,
                    max_playload double precision,
                    battery_type character varying(225),
                    battery_capacity character varying(225)
                );
            """)
            conn.commit()
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL or creating table: {e}")
        return None
    
    
get_db_connection()

@app.route('/api/drones', methods=['GET'])
def get_drones_api():
    conn = get_db_connection()
    drones_list = []
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, drone_id, drone_name, model, drone_type,
                           weight, max_playload, battery_type, battery_capacity
                    FROM dronesdata ORDER BY id ASC
                """)
                raw_drones = cur.fetchall()
                if raw_drones:
                    columns = [desc[0].lower() for desc in cur.description]
                    drones_list = [dict(zip(columns, row)) for row in raw_drones]
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
    if request.method == 'POST':
        drone_id_val = request.form.get('drone_id')
        drone_name = request.form.get('drone_name')
        weight_str = request.form.get('weight')
        max_playload_str = request.form.get('max_playload')
        model = request.form.get('model')
        drone_type = request.form.get('drone_type')
        battery_type = request.form.get('battery_type')
        battery_capacity = request.form.get('battery_capacity')

        if not drone_id_val or not drone_name:
            return jsonify({"message": "Drone ID and Drone Name are required.", "error": True}), 400

        weight = None
        if weight_str and weight_str.strip():
            try: 
                weight = float(weight_str)
            except ValueError:
                return jsonify({"message": "Invalid input for Weight. Please enter a valid number.", "error": True}), 400
        
        max_playload = None
        if max_playload_str and max_playload_str.strip():
            try: 
                max_playload = float(max_playload_str)
            except ValueError:
                return jsonify({"message": "Invalid input for Max Payload. Please enter a valid number.", "error": True}), 400

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM dronesdata WHERE drone_id = %s", (drone_id_val,))
                    if cur.fetchone():
                        return jsonify({"message": f"Drone with ID '{drone_id_val}' already exists. Cannot add duplicate.", "error": True}), 409
                    else:
                        sql = """
                            INSERT INTO dronesdata (drone_id, drone_name, model, drone_type, weight, max_playload, battery_type, battery_capacity)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cur.execute(sql, (drone_id_val, drone_name, model, drone_type, weight, max_playload, battery_type, battery_capacity))
                        conn.commit()
                        return jsonify({"message": "Drone added successfully!", "drone_id": drone_id_val}), 201
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
    if request.method == 'POST':
        original_drone_id_val = request.form.get('original_drone_id')
        drone_id_val = request.form.get('drone_id')
        drone_name = request.form.get('drone_name')
        model = request.form.get('model')
        drone_type = request.form.get('drone_type')
        weight_str = request.form.get('weight')
        max_playload_str = request.form.get('max_playload')
        battery_type = request.form.get('battery_type')
        battery_capacity = request.form.get('battery_capacity')

        if not drone_id_val or not drone_name:
            return jsonify({"message": "Drone ID and Drone Name are required.", "error": True}), 400
        
        weight = None
        if weight_str and weight_str.strip():
            try: 
                weight = float(weight_str)
            except ValueError: 
                return jsonify({"message": "Invalid Weight. Must be a number.", "error": True}), 400
        
        max_playload = None
        if max_playload_str and max_playload_str.strip():
            try: 
                max_playload = float(max_playload_str)
            except ValueError: 
                return jsonify({"message": "Invalid Max Payload. Must be a number.", "error": True}), 400

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    if drone_id_val != original_drone_id_val:
                         cur.execute("SELECT id FROM dronesdata WHERE drone_id = %s AND id != %s", (drone_id_val, drone_db_id))
                         if cur.fetchone():
                            return jsonify({"message": f"Another drone with ID '{drone_id_val}' already exists. Update failed.", "error": True}), 409

                    # Update the main drone record
                    sql = """
                        UPDATE dronesdata
                        SET drone_id = %s, drone_name = %s, model = %s, drone_type = %s,
                            weight = %s, max_playload = %s, battery_type = %s, battery_capacity = %s
                        WHERE id = %s
                    """
                    cur.execute(sql, (drone_id_val, drone_name, model, drone_type,
                                      weight, max_playload, battery_type, battery_capacity,
                                      drone_db_id))
                    
                    # Update related tables if drone_id or drone_name changed
                    if drone_id_val != original_drone_id_val or drone_name != request.form.get('original_drone_name', ''):
                        
                        # Check if droneassignment table exists and has records to update
                        try:
                            cur.execute("""
                                SELECT COUNT(*) FROM information_schema.tables 
                                WHERE table_name = 'droneassignment'
                            """)
                            if cur.fetchone()[0] > 0:
                                # Check if there are records with the original drone_id
                                cur.execute("SELECT COUNT(*) FROM droneassignment WHERE drone_id = %s", (original_drone_id_val,))
                                if cur.fetchone()[0] > 0:
                                    cur.execute("""
                                        UPDATE droneassignment 
                                        SET drone_id = %s, drone_name = %s 
                                        WHERE drone_id = %s
                                    """, (drone_id_val, drone_name, original_drone_id_val))
                                    print(f"Updated droneassignment table: {cur.rowcount} rows affected")
                                else:
                                    print("No records found in droneassignment table to update")
                            else:
                                print("droneassignment table does not exist")
                        except psycopg2.Error as e:
                            print(f"Warning: Could not update droneassignment table: {e}")
                        
                        # Check if packagemanagement table exists and has records to update
                        try:
                            cur.execute("""
                                SELECT COUNT(*) FROM information_schema.tables 
                                WHERE table_name = 'packagemanagement'
                            """)
                            if cur.fetchone()[0] > 0:
                                # Check if the table has the correct column name
                                cur.execute("""
                                    SELECT column_name FROM information_schema.columns 
                                    WHERE table_name = 'packagemanagement' 
                                    AND column_name IN ('drone_id', 'assigned_drone_id')
                                """)
                                columns = [row[0] for row in cur.fetchall()]
                                
                                if 'assigned_drone_id' in columns:
                                    # Check if there are records with the original drone_id
                                    cur.execute("SELECT COUNT(*) FROM packagemanagement WHERE assigned_drone_id = %s", (original_drone_id_val,))
                                    if cur.fetchone()[0] > 0:
                                        cur.execute("""
                                            UPDATE packagemanagement 
                                            SET assigned_drone_id = %s 
                                            WHERE assigned_drone_id = %s
                                        """, (drone_id_val, original_drone_id_val))
                                        print(f"Updated packagemanagement table: {cur.rowcount} rows affected")
                                    else:
                                        print("No records found in packagemanagement table to update")
                                elif 'drone_id' in columns:
                                    # Check if there are records with the original drone_id
                                    cur.execute("SELECT COUNT(*) FROM packagemanagement WHERE drone_id = %s", (original_drone_id_val,))
                                    if cur.fetchone()[0] > 0:
                                        cur.execute("""
                                            UPDATE packagemanagement 
                                            SET drone_id = %s 
                                            WHERE drone_id = %s
                                        """, (drone_id_val, original_drone_id_val))
                                        print(f"Updated packagemanagement table: {cur.rowcount} rows affected")
                                    else:
                                        print("No records found in packagemanagement table to update")
                                else:
                                    print("packagemanagement table does not have drone_id or assigned_drone_id column")
                            else:
                                print("packagemanagement table does not exist")
                        except psycopg2.Error as e:
                            print(f"Warning: Could not update packagemanagement table: {e}")
                    
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
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # First, get the drone_id before deletion for updating related tables
                cur.execute("SELECT drone_id FROM dronesdata WHERE id = %s", (drone_db_id,))
                drone_record = cur.fetchone()
                
                if drone_record is None:
                    return jsonify({"message": f"Drone with Sys. ID {drone_db_id} not found.", "error": True}), 404
                
                drone_id_to_delete = drone_record[0]
                
                # Check if droneassignment table exists and has records to update
                try:
                    cur.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_name = 'droneassignment'
                    """)
                    if cur.fetchone()[0] > 0:
                        # Check if there are records with the drone_id
                        cur.execute("SELECT COUNT(*) FROM droneassignment WHERE drone_id = %s", (drone_id_to_delete,))
                        if cur.fetchone()[0] > 0:
                            cur.execute("""
                                UPDATE droneassignment 
                                SET drone_id = NULL, drone_name = NULL 
                                WHERE drone_id = %s
                            """, (drone_id_to_delete,))
                            print(f"Updated droneassignment table: {cur.rowcount} rows affected")
                        else:
                            print("No records found in droneassignment table to update")
                    else:
                        print("droneassignment table does not exist")
                except psycopg2.Error as e:
                    print(f"Warning: Could not update droneassignment table: {e}")
                
                # Check if packagemanagement table exists and has records to update
                try:
                    cur.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_name = 'packagemanagement'
                    """)
                    if cur.fetchone()[0] > 0:
                        # Check if the table has the correct column name
                        cur.execute("""
                            SELECT column_name FROM information_schema.columns 
                            WHERE table_name = 'packagemanagement' 
                            AND column_name IN ('drone_id', 'assigned_drone_id')
                        """)
                        columns = [row[0] for row in cur.fetchall()]
                        
                        if 'assigned_drone_id' in columns:
                            # Check if there are records with the drone_id
                            cur.execute("SELECT COUNT(*) FROM packagemanagement WHERE assigned_drone_id = %s", (drone_id_to_delete,))
                            if cur.fetchone()[0] > 0:
                                cur.execute("""
                                    UPDATE packagemanagement 
                                    SET assigned_drone_id = NULL 
                                    WHERE assigned_drone_id = %s
                                """, (drone_id_to_delete,))
                                print(f"Updated packagemanagement table: {cur.rowcount} rows affected")
                            else:
                                print("No records found in packagemanagement table to update")
                        elif 'drone_id' in columns:
                            # Check if there are records with the drone_id
                            cur.execute("SELECT COUNT(*) FROM packagemanagement WHERE drone_id = %s", (drone_id_to_delete,))
                            if cur.fetchone()[0] > 0:
                                cur.execute("""
                                    UPDATE packagemanagement 
                                    SET drone_id = NULL 
                                    WHERE drone_id = %s
                                """, (drone_id_to_delete,))
                                print(f"Updated packagemanagement table: {cur.rowcount} rows affected")
                            else:
                                print("No records found in packagemanagement table to update")
                        else:
                            print("packagemanagement table does not have drone_id or assigned_drone_id column")
                    else:
                        print("packagemanagement table does not exist")
                except psycopg2.Error as e:
                    print(f"Warning: Could not update packagemanagement table: {e}")
                
                # Finally, delete the drone from dronesdata
                cur.execute("DELETE FROM dronesdata WHERE id = %s", (drone_db_id,))
                
            conn.commit()
            return jsonify({"message": f"Drone {drone_db_id} deleted successfully and related records updated!"}), 200
        except psycopg2.Error as e:
            conn.rollback()
            print(f"Database error deleting drone: {e}")
            return jsonify({"message": f"Error deleting drone: {e}", "error": True}), 500
        finally:
            conn.close()
    else:
        return jsonify({"message": "Could not connect to the database to delete drone.", "error": True}), 500

@app.route('/export_csv')
def export_csv():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed, cannot export CSV.", "error")
        return redirect(url_for('index'))

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, drone_id, drone_name, model, drone_type, weight, max_playload, battery_type, battery_capacity FROM dronesdata ORDER BY id ASC")
            rows = cur.fetchall()
            column_names = [desc[0] for desc in cur.description]

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(column_names)
        cw.writerows(rows)
        output = si.getvalue()
        si.close()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=drones_export.csv"}
        )
    except psycopg2.Error as e:
        flash(f"Error exporting CSV: {e}", "error")
        print(f"Error exporting CSV: {e}")
        return redirect(url_for('index'))
    finally:
        if conn:
            conn.close()

@app.route('/import_csv', methods=['POST'])
def import_csv():
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
        expected_headers = ['drone_id', 'drone_name', 'model', 'drone_type', 'weight', 'max_playload', 'battery_type', 'battery_capacity']
        messages = []

        try:
            stream = io.TextIOWrapper(file.stream, encoding='utf-8', newline='')
            csv_reader = csv.reader(stream)
            header = next(csv_reader)
            if not header or [h.strip().lower() for h in header] != [eh.lower() for eh in expected_headers]:
                actual_headers_str = ", ".join(header) if header else "None"
                expected_headers_str = ", ".join(expected_headers)
                return jsonify({"message": f"CSV file has incorrect headers. Expected: '{expected_headers_str}'. Found: '{actual_headers_str}'. Please ensure the CSV headers match.", "error": True}), 400

            with conn.cursor() as cur:
                for row_number, row in enumerate(csv_reader, start=2):
                    if len(row) != len(expected_headers):
                        messages.append(f"Row {row_number}: Incorrect number of columns. Skipping.")
                        skipped_count += 1
                        continue
                    
                    row_data = dict(zip(expected_headers, row))
                    drone_id_val = row_data.get('drone_id', '').strip()
                    drone_name = row_data.get('drone_name', '').strip()
                    
                    if not drone_id_val or not drone_name:
                        messages.append(f"Row {row_number}: Drone ID or Drone Name is missing. Skipping.")
                        skipped_count += 1
                        continue

                    cur.execute("SELECT id FROM dronesdata WHERE drone_id = %s", (drone_id_val,))
                    if cur.fetchone():
                        messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): Already exists. Skipping.")
                        skipped_count += 1
                        continue
                    
                    model = row_data.get('model', '').strip() or None
                    drone_type = row_data.get('drone_type', '').strip() or None
                    weight_str = row_data.get('weight', '').strip()
                    weight = None
                    if weight_str:
                        try: 
                            weight = float(weight_str)
                        except ValueError: 
                            messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): Invalid weight value '{weight_str}'. Skipping.")
                            skipped_count += 1
                            continue
                    
                    max_playload_str = row_data.get('max_playload', '').strip()
                    max_playload = None
                    if max_playload_str:
                        try: 
                            max_playload = float(max_playload_str)
                        except ValueError:
                            messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): Invalid max_playload value '{max_playload_str}'. Skipping.")
                            skipped_count += 1
                            continue
                    
                    battery_type = row_data.get('battery_type', '').strip() or None
                    battery_capacity = row_data.get('battery_capacity', '').strip() or None

                    try:
                        sql = """
                            INSERT INTO dronesdata (drone_id, drone_name, model, drone_type, weight, max_playload, battery_type, battery_capacity)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cur.execute(sql, (drone_id_val, drone_name, model, drone_type, weight, max_playload, battery_type, battery_capacity))
                        imported_count += 1
                    except psycopg2.Error as db_err:
                        messages.append(f"Row {row_number} (Drone ID: {drone_id_val}): DB error: {db_err}. Skipping.")
                        error_count += 1
                        conn.rollback()
                    
                conn.commit()
            
            summary_message = f"CSV Import Complete: {imported_count} rows imported, {skipped_count} skipped, {error_count} DB errors."
            messages.insert(0, summary_message)
            return jsonify({"message": "\n".join(messages), "imported_count": imported_count, "skipped_count": skipped_count, "error_count": error_count}), 200

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)