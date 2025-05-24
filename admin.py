import psycopg2
import psycopg2.extras
import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Database connection details (ensure these are correct)
DB_HOST = "dpg-d0op2vuuk2gs738trhhg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_3wh9"
DB_USER = "shadowfly_3wh9_user"
DB_PASS = "4eX3uM5s2uX0wry7PFVG5YnqKOHUXFmF" # Consider using environment variables for passwords
DB_PORT = 5432

# Setup logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)


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
    except psycopg2.OperationalError as e:
        app.logger.error(f"!!! Database connection failed: {e}")
        raise

def create_tables():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create ddts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ddts (
                id SERIAL PRIMARY KEY,
                name CHARACTER VARYING(255) NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                status CHARACTER VARYING(255)
            );
        """)
        app.logger.info("Table 'ddts' ensured to exist.")

        # Create warehouses table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS warehouses (
                id SERIAL PRIMARY KEY,
                name CHARACTER VARYING(255) NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION
            );
        """)
        app.logger.info("Table 'warehouses' ensured to exist.")

        # Create droneassignment table (Corrected based on the provided image)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS droneassignment (
                id SERIAL, -- Creates an auto-incrementing integer, implies NOT NULL and a sequence
                drone_id CHARACTER VARYING(225) NOT NULL,
                drone_name CHARACTER VARYING(225), -- Nullable as per image
                name CHARACTER VARYING(225) NOT NULL, -- This 'name' refers to warehouse name
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION, -- Corrected typo from 'logitude' in image
                status CHARACTER VARYING(225),
                CONSTRAINT droneassignment_pkey PRIMARY KEY (drone_id, name) -- Composite primary key
            );
        """)
        app.logger.info("Table 'droneassignment' ensured to exist with corrected schema.")
        
        # It's good practice to also create the packagemanagement table definition
        # if it's being used elsewhere in your code, e.g., in update_warehouse
        # For now, assuming it might be created separately or you'll add it.
        # Example:
        # cur.execute("""
        #     CREATE TABLE IF NOT EXISTS packagemanagement (
        #         package_id SERIAL PRIMARY KEY,
        #         warehouse_name CHARACTER VARYING(255),
        #         -- other columns...
        #         FOREIGN KEY (warehouse_name) REFERENCES warehouses(name) -- Example foreign key
        #     );
        # """)
        # app.logger.info("Table 'packagemanagement' ensured to exist.")

        conn.commit()
    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"Error creating tables: {e}")
        if conn: conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()

# --- Rest of your Flask application code ---

create_tables() # Call this once at startup to ensure tables exist


@app.route('/add_ddt', methods=['POST'])
def add_ddt():
    data = request.json
    app.logger.info(f"[DEBUG][ADD DDT] Received data: {data}")
    name = data.get('name')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    status = data.get('status', 'Active')

    if not name or latitude is None or longitude is None:
        app.logger.warning(f"[DEBUG][ADD DDT] Missing required fields. Name: {name}, Lat: {latitude}, Lon: {longitude}")
        return jsonify({'error': 'Missing required fields (name, latitude, longitude)'}), 400

    try:
        lat_float = float(latitude)
        lon_float = float(longitude)
    except ValueError:
        app.logger.warning(f"[DEBUG][ADD DDT] Invalid lat/lon format. Lat: {latitude}, Lon: {longitude}")
        return jsonify({'error': 'Invalid latitude or longitude format. Must be numbers.'}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        sql = """
            INSERT INTO ddts (name, latitude, longitude, status)
            VALUES (%s, %s, %s, %s)
            RETURNING id, name, latitude, longitude, status
            """
        values = (name, lat_float, lon_float, status)
        app.logger.info(f"[DEBUG][ADD DDT] Executing SQL: {sql} with values: {values}")
        cur.execute(sql, values)
        new_ddt_record = cur.fetchone()
        app.logger.info(f"[DEBUG][ADD DDT] Record from DB after INSERT: {new_ddt_record}")

        if new_ddt_record:
            conn.commit()
            app.logger.info("[DEBUG][ADD DDT] Insert committed.")
            ddt_to_return = dict(new_ddt_record)
            ddt_to_return['latitude'] = float(ddt_to_return['latitude'])
            ddt_to_return['longitude'] = float(ddt_to_return['longitude'])
            return jsonify({'message': 'DDT added successfully', 'ddt': ddt_to_return}), 201
        else:
            app.logger.error("[DEBUG][ADD DDT] Failed to retrieve added DDT after insertion (fetchone returned None).")
            if conn: conn.rollback()
            return jsonify({'error': 'Failed to retrieve added DDT after insertion'}), 500

    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][ADD DDT] Error: {e}")
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/add_warehouse', methods=['POST'])
def add_warehouse():
    data = request.json
    app.logger.info(f"[DEBUG][ADD WAREHOUSE] Received data: {data}")
    name = data.get('name')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if not name or latitude is None or longitude is None:
        app.logger.warning(f"[DEBUG][ADD WAREHOUSE] Missing required fields. Name: {name}, Lat: {latitude}, Lon: {longitude}")
        return jsonify({'error': 'Missing required fields (name, latitude, longitude)'}), 400

    try:
        lat_float = float(latitude)
        lon_float = float(longitude)
    except ValueError:
        app.logger.warning(f"[DEBUG][ADD WAREHOUSE] Invalid lat/lon format. Lat: {latitude}, Lon: {longitude}")
        return jsonify({'error': 'Invalid latitude or longitude format. Must be numbers.'}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql = """
            INSERT INTO warehouses (name, latitude, longitude)
            VALUES (%s, %s, %s)
            RETURNING id, name, latitude, longitude
            """
        values = (name, lat_float, lon_float)
        app.logger.info(f"[DEBUG][ADD WAREHOUSE] Executing SQL: {sql} with values: {values}")
        cur.execute(sql, values)
        new_warehouse_record = cur.fetchone()
        app.logger.info(f"[DEBUG][ADD WAREHOUSE] Record from DB after INSERT: {new_warehouse_record}")

        if new_warehouse_record:
            conn.commit()
            app.logger.info("[DEBUG][ADD WAREHOUSE] Insert committed.")
            warehouse_to_return = dict(new_warehouse_record)
            warehouse_to_return['latitude'] = float(warehouse_to_return['latitude'])
            warehouse_to_return['longitude'] = float(warehouse_to_return['longitude'])
            return jsonify({'message': 'Warehouse added successfully', 'warehouse': warehouse_to_return}), 201
        else:
            app.logger.error("[DEBUG][ADD WAREHOUSE] Failed to retrieve added warehouse after insertion.")
            if conn: conn.rollback()
            return jsonify({'error': 'Failed to retrieve added warehouse after insertion'}), 500

    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][ADD WAREHOUSE] Error: {e}")
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/get_ddts', methods=['GET'])
def get_ddts_route():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT
                ROW_NUMBER() OVER (ORDER BY id) as sequential_id,
                id,
                name,
                latitude,
                longitude,
                status
            FROM
                ddts
            ORDER BY
                id;
        """)
        ddts_records = cur.fetchall()

        result_list = []
        for row in ddts_records:
            ddt_item = dict(row)
            ddt_item['latitude'] = float(ddt_item['latitude'])
            ddt_item['longitude'] = float(ddt_item['longitude'])
            result_list.append(ddt_item)

        return jsonify(result_list), 200
    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][GET DDTS] Error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/get_warehouses', methods=['GET'])
def get_warehouses_route():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT
                ROW_NUMBER() OVER (ORDER BY id) as sequential_id,
                id,
                name,
                latitude,
                longitude
            FROM
                warehouses
            ORDER BY
                id;
        """)
        warehouses_records = cur.fetchall()

        result_list = []
        for row in warehouses_records:
            wh_item = dict(row)
            wh_item['latitude'] = float(wh_item['latitude'])
            wh_item['longitude'] = float(wh_item['longitude'])
            result_list.append(wh_item)

        return jsonify(result_list), 200
    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][GET WAREHOUSES] Error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/update_ddt/<int:ddt_id>', methods=['PUT'])
def update_ddt(ddt_id):
    data = request.json
    app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Received data: {data}")

    name = data.get('name')
    status = data.get('status')
    app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Extracted name: '{name}', status: '{status}'")

    if name is None and status is None:
        app.logger.warning(f"[DEBUG][UPDATE DDT ID: {ddt_id}] No data provided for update (name and status are None).")
        return jsonify({'error': 'No data provided for update (name or status required)'}), 400

    update_fields = []
    update_values = []

    if name is not None:
        update_fields.append("name = %s")
        update_values.append(name)
    if status is not None:
        if status not in ['Active', 'Inactive']:
            app.logger.error(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Invalid status value received: {status}")
            return jsonify({'error': 'Invalid status value. Must be "Active" or "Inactive".'}), 400
        update_fields.append("status = %s")
        update_values.append(status)

    if not update_fields:
        app.logger.warning(f"[DEBUG][UPDATE DDT ID: {ddt_id}] No valid fields to update after processing.")
        return jsonify({'error': 'No valid fields to update'}), 400

    update_values.append(ddt_id)

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        sql = f"UPDATE ddts SET {', '.join(update_fields)} WHERE id = %s RETURNING id, name, latitude, longitude, status"
        app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Executing SQL: {sql} with values: {tuple(update_values)}")

        cur.execute(sql, tuple(update_values))
        updated_ddt_record = cur.fetchone()
        app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Record from DB after UPDATE (fetchone): {updated_ddt_record}")

        if updated_ddt_record:
            conn.commit()
            app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Update committed to DB.")
            ddt_to_return = dict(updated_ddt_record)
            ddt_to_return['latitude'] = float(ddt_to_return['latitude'])
            ddt_to_return['longitude'] = float(ddt_to_return['longitude'])
            return jsonify({'message': 'DDT updated successfully', 'ddt': ddt_to_return}), 200
        else:
            app.logger.warning(f"[DEBUG][UPDATE DDT ID: {ddt_id}] DDT not found or no changes made (fetchone returned None).")
            if conn: conn.rollback()
            return jsonify({'error': 'DDT not found or no effective changes made'}), 404

    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Error: {e}", exc_info=True)
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()
@app.route('/delete_ddt/<int:ddt_id>', methods=['DELETE'])
def delete_ddt(ddt_id):
    app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Request received.")
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Step 1: Get the name of the DDT
        cur.execute("SELECT name FROM ddts WHERE id = %s", (ddt_id,))
        name_result = cur.fetchone()
        app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Name fetched: {name_result}")

        if not name_result:
            app.logger.warning(f"[DEBUG][DELETE DDT ID: {ddt_id}] DDT not found.")
            return jsonify({'error': f'DDT {ddt_id} not found'}), 404

        ddt_name = name_result[0]

        # Step 2: Get latitude and longitude using the name
        cur.execute("SELECT latitude, longitude FROM ddts WHERE name = %s", (ddt_name,))
        coord_result = cur.fetchone()
        app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Coordinates fetched: {coord_result}")

        if coord_result:
            latitude, longitude = coord_result

            # Step 3: Delete from packagemanagement where coordinates match
            cur.execute("""
                UPDATE packagemanagement
                SET destination_lat = NULL, destination_lng = NULL
                WHERE destination_lat = %s AND destination_lng = %s
            """, (latitude, longitude))
            app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Related packagemanagement entries deleted.")

        # Step 4: Delete from ddts table
        cur.execute("DELETE FROM ddts WHERE id = %s RETURNING id", (ddt_id,))
        deleted_id_tuple = cur.fetchone()
        app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Result from DB after DELETE (fetchone): {deleted_id_tuple}")

        if deleted_id_tuple:
            conn.commit()
            app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Delete committed.")
            return jsonify({'message': f'DDT {ddt_id} and related entries deleted successfully'}), 200
        else:
            if conn: conn.rollback()
            app.logger.warning(f"[DEBUG][DELETE DDT ID: {ddt_id}] DDT not found for deletion.")
            return jsonify({'error': f'DDT {ddt_id} not found'}), 404

    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][DELETE DDT ID: {ddt_id}] Error: {e}", exc_info=True)
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


@app.route('/update_warehouse/<int:warehouse_id>', methods=['PUT'])
def update_warehouse(warehouse_id):
    data = request.json
    app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Received data: {data}")
    new_name = data.get('name')

    if new_name is None:
        app.logger.warning(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Missing required field: name.")
        return jsonify({'error': 'Missing required field: name'}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("SELECT name FROM warehouses WHERE id = %s", (warehouse_id,))
        old_warehouse_record = cur.fetchone()

        if not old_warehouse_record:
            app.logger.warning(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Warehouse not found.")
            return jsonify({'error': 'Warehouse not found'}), 404
        
        old_warehouse_name = old_warehouse_record['name']
        app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Old warehouse name: '{old_warehouse_name}'")

        sql_update_warehouse = "UPDATE warehouses SET name = %s WHERE id = %s RETURNING id, name, latitude, longitude"
        app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] SQL (warehouses): {sql_update_warehouse} Data: {(new_name, warehouse_id)}")
        cur.execute(sql_update_warehouse, (new_name, warehouse_id))
        updated_warehouse_record = cur.fetchone()
        app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] DB Result (warehouses): {updated_warehouse_record}")

        if updated_warehouse_record:
            if old_warehouse_name != new_name:
                # In droneassignment, the 'name' column refers to the warehouse name
                sql_update_droneassignment = "UPDATE droneassignment SET name = %s WHERE name = %s"
                app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] SQL (droneassignment): {sql_update_droneassignment} Data: {(new_name, old_warehouse_name)}")
                cur.execute(sql_update_droneassignment, (new_name, old_warehouse_name))
                app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Updated droneassignment table. {cur.rowcount} rows affected.")
                
                # Update packagemanagement table as well
                # Ensure 'packagemanagement' table and 'warehouse_name' column exist
                try:
                    sql_update_packagemanagement = "UPDATE packagemanagement SET warehouse_name = %s WHERE warehouse_name = %s"
                    app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] SQL (packagemanagement): {sql_update_packagemanagement} Data: {(new_name, old_warehouse_name)}")
                    cur.execute(sql_update_packagemanagement, (new_name, old_warehouse_name))
                    app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Updated packagemanagement table. {cur.rowcount} rows affected.")
                except psycopg2.Error as pm_error:
                    # Log if packagemanagement table doesn't exist or schema is different, but don't fail the whole operation
                    app.logger.warning(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Could not update packagemanagement (may not exist or schema mismatch): {pm_error}")


            conn.commit()
            app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Committed.")
            warehouse_to_return = dict(updated_warehouse_record)
            warehouse_to_return['latitude'] = float(warehouse_to_return['latitude'])
            warehouse_to_return['longitude'] = float(warehouse_to_return['longitude'])
            return jsonify({'message': 'Warehouse updated successfully, and relevant assignments synced.', 'warehouse': warehouse_to_return}), 200
        else:
            app.logger.warning(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Warehouse not found during update or no change made.")
            if conn: conn.rollback() 
            return jsonify({'error': 'Warehouse not found or no effective changes made'}), 404

    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Error: {e}", exc_info=True)
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


@app.route('/delete_warehouse/<int:warehouse_id>', methods=['DELETE'])
def delete_warehouse(warehouse_id):
    app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Request.")
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("SELECT name FROM warehouses WHERE id = %s", (warehouse_id,))
        warehouse_record = cur.fetchone()

        if not warehouse_record:
            app.logger.warning(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Warehouse not found.")
            return jsonify({'error': f'Warehouse {warehouse_id} not found'}), 404
        
        warehouse_name_to_delete = warehouse_record['name']
        app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Warehouse name to delete: '{warehouse_name_to_delete}'")

        # Delete associated drone assignments (name column in droneassignment is warehouse_name)
        sql_delete_assignments = "DELETE FROM droneassignment WHERE name = %s"
        app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] SQL (droneassignment): {sql_delete_assignments} Data: {warehouse_name_to_delete}")
        cur.execute(sql_delete_assignments, (warehouse_name_to_delete,))
        app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Deleted {cur.rowcount} assignments from droneassignment table.")

        # Delete associated package management entries
        # Ensure 'packagemanagement' table and 'warehouse_name' column exist
        try:
            sql_delete_packages = "DELETE FROM packagemanagement WHERE warehouse_name = %s"
            app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] SQL (packagemanagement): {sql_delete_packages} Data: {warehouse_name_to_delete}")
            cur.execute(sql_delete_packages, (warehouse_name_to_delete,))
            app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Deleted {cur.rowcount} packages from packagemanagement table.")
        except psycopg2.Error as pm_error:
            app.logger.warning(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Could not delete from packagemanagement (may not exist or schema mismatch): {pm_error}")


        # Delete the warehouse
        cur.execute("DELETE FROM warehouses WHERE id = %s RETURNING id", (warehouse_id,))
        deleted_id_tuple = cur.fetchone() 
        app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] DB Result (warehouses): {deleted_id_tuple}")
        
        if deleted_id_tuple: 
            conn.commit()
            app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Committed.")
            return jsonify({'message': f'Warehouse {warehouse_id} ({warehouse_name_to_delete}), its associated drone assignments, and packages deleted successfully'}), 200
        else:
            app.logger.warning(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Warehouse not found during final delete step, though initial fetch succeeded (unexpected).")
            if conn: conn.rollback()
            return jsonify({'error': f'Warehouse {warehouse_id} not found during final delete step'}), 404

    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Error: {e}", exc_info=True)
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


@app.route('/get_drone_assignments_by_warehouse_name/<string:warehouse_name>', methods=['GET'])
def get_drone_assignments_by_warehouse_name(warehouse_name):
    app.logger.info(f"[DEBUG][GET ASSIGNMENTS] For warehouse: {warehouse_name}")
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # The 'name' column in droneassignment is the warehouse name.
        # The image shows id, drone_id, drone_name, name, latitude, longitude, status.
        # We should select relevant columns for display.
        sql = """
            SELECT id, drone_id, drone_name, latitude, longitude, status
            FROM droneassignment
            WHERE name = %s
            ORDER BY id 
        """ # Assuming 'id' is the preferred ordering for assignments within a warehouse
        cur.execute(sql, (warehouse_name,))
        assignments_records = cur.fetchall()

        result_list = []
        for row in assignments_records:
            item = dict(row)
            # Ensure latitude and longitude are floats if they exist
            if item.get('latitude') is not None:
                item['latitude'] = float(item['latitude'])
            if item.get('longitude') is not None:
                item['longitude'] = float(item['longitude'])
            result_list.append(item)
            
        return jsonify(result_list), 200

    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][GET ASSIGNMENTS] Error for {warehouse_name}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

if __name__ == '__main__':
    app.logger.info("Starting Flask application on http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)