import psycopg2
import psycopg2.extras
import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Database connection details (ensure these are correct)
DB_HOST = "dpg-d1aovm6uk2gs7390cttg-a.oregon-postgres.render.com"
DB_NAME = "shadowfly_um2n"
DB_USER = "shadowfly_um2n_user"
DB_PASS = "6ab9pofT8Tv0H5TqLWiD0qJZ0fTR8aNk"
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
                status CHARACTER VARYING(255),
                rack_01  CHARACTER VARYING(255) ,
                rack_02  CHARACTER VARYING(255) ,
                rack_03  CHARACTER VARYING(255) ,
                rack_04  CHARACTER VARYING(255) ,
                rack_05  CHARACTER VARYING(255) ,
                rack_06  CHARACTER VARYING(255) ,
                total_racks INTEGER,
                avialable_racks INTEGER
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
    total_racks = data.get('total_racks')

    # Validate required fields
    if not name or latitude is None or longitude is None or total_racks is None:
        app.logger.warning(f"[DEBUG][ADD DDT] Missing required fields. Name: {name}, Lat: {latitude}, Lon: {longitude}, Total Racks: {total_racks}")
        return jsonify({'error': 'Missing required fields (name, latitude, longitude, total_racks)'}), 400

    # Validate latitude and longitude
    try:
        lat_float = float(latitude)
        lon_float = float(longitude)
    except ValueError:
        app.logger.warning(f"[DEBUG][ADD DDT] Invalid lat/lon format. Lat: {latitude}, Lon: {longitude}")
        return jsonify({'error': 'Invalid latitude or longitude format. Must be numbers.'}), 400

    # Validate total_racks
    try:
        total_racks_int = int(total_racks)
        if total_racks_int < 0 or total_racks_int > 6:
            app.logger.warning(f"[DEBUG][ADD DDT] Invalid total_racks value: {total_racks}. Must be between 0 and 6.")
            return jsonify({'error': 'Total racks must be a number between 0 and 6.'}), 400
    except ValueError:
        app.logger.warning(f"[DEBUG][ADD DDT] Invalid total_racks format: {total_racks}")
        return jsonify({'error': 'Total racks must be a valid integer.'}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        sql = """
            INSERT INTO ddts (
                name, latitude, longitude, status, 
                rack_01, rack_02, rack_03, rack_04, rack_05, rack_06, 
                total_racks, avialable_racks
            )
            VALUES (%s, %s, %s, %s, NULL, NULL, NULL, NULL, NULL, NULL, %s, NULL)
            RETURNING id, name, latitude, longitude, status, total_racks
            """
        values = (name, lat_float, lon_float, status, total_racks_int)
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
            ddt_to_return['total_racks'] = int(ddt_to_return['total_racks']) if ddt_to_return['total_racks'] is not None else None
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
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Extracted name: '{name}', status: '{status}', latitude: '{latitude}', longitude: '{longitude}'")

    if name is None and status is None and latitude is None and longitude is None:
        app.logger.warning(f"[DEBUG][UPDATE DDT ID: {ddt_id}] No data provided for update.")
        return jsonify({'error': 'No data provided for update'}), 400

    update_fields = []
    update_values = []

    # Initialize new_name to None if it's not provided in the request
    # This prevents the "name 'new_name' is not defined" error
    new_name = name # Assign 'name' (from request) to new_name

    if name is not None:
        update_fields.append("name = %s")
        update_values.append(name)
    if status is not None:
        if status not in ['Active', 'Inactive']:
            app.logger.error(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Invalid status value received: {status}")
            return jsonify({'error': 'Invalid status value. Must be "Active" or "Inactive".'}), 400
        update_fields.append("status = %s")
        update_values.append(status)
    if latitude is not None:
        try:
            lat_float = float(latitude)
            update_fields.append("latitude = %s")
            update_values.append(lat_float)
        except ValueError:
            app.logger.error(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Invalid latitude value: {latitude}")
            return jsonify({'error': 'Invalid latitude value. Must be a number.'}), 400
    if longitude is not None:
        try:
            lng_float = float(longitude)
            update_fields.append("longitude = %s")
            update_values.append(lng_float)
        except ValueError:
            app.logger.error(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Invalid longitude value: {longitude}")
            return jsonify({'error': 'Invalid longitude value. Must be a number.'}), 400

    if not update_fields:
        app.logger.warning(f"[DEBUG][UPDATE DDT ID: {ddt_id}] No valid fields to update after processing.")
        return jsonify({'error': 'No valid fields to update'}), 400

    update_values.append(ddt_id)

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Get the old DDT name before updating (if name is being changed)
        old_ddt_name = None
        # Always fetch the old name, even if a new name isn't provided in this request
        cur.execute("SELECT name FROM ddts WHERE id = %s", (ddt_id,))
        old_ddt_record = cur.fetchone()
        if old_ddt_record:
            old_ddt_name = old_ddt_record['name']
            app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Old DDT name: '{old_ddt_name}'")


        sql = f"UPDATE ddts SET {', '.join(update_fields)} WHERE id = %s RETURNING id, name, latitude, longitude, status"
        app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Executing SQL: {sql} with values: {tuple(update_values)}")

        cur.execute(sql, tuple(update_values))
        updated_ddt_record = cur.fetchone()
        app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Record from DB after UPDATE (fetchone): {updated_ddt_record}")

        if updated_ddt_record:
            conn.commit()
            app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Update committed.")
            ddt_to_return = dict(updated_ddt_record)
            ddt_to_return['latitude'] = float(ddt_to_return['latitude'])
            ddt_to_return['longitude'] = float(ddt_to_return['longitude'])

            # If the name was changed, update users_data
            # Use 'name' from the request, as it's the new name being applied
            if name is not None and old_ddt_name and old_ddt_name != name:
                try:
                    cur.execute("UPDATE users_data SET assigned_ddt = %s WHERE assigned_ddt = %s", (name, old_ddt_name))
                    app.logger.info(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Updated users_data table. {cur.rowcount} rows affected.")
                    conn.commit()
                except psycopg2.Error as user_data_error:
                    app.logger.warning(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Could not update users_data (may not exist or schema mismatch): {user_data_error}")
                    conn.rollback()

            return jsonify({'message': 'DDT updated successfully', 'ddt': ddt_to_return}), 200
        else:
            app.logger.warning(f"[DEBUG][UPDATE DDT ID: {ddt_id}] DDT not found during update or no change made.")
            if conn: conn.rollback()
            return jsonify({'error': 'DDT not found or no effective changes made'}), 404

    except (Exception, psycopg2.Error) as e:
        app.logger.error(f"[DEBUG][UPDATE DDT ID: {ddt_id}] Error: {e}", exc_info=True)
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

# Update the delete_ddt function to set packagemanagement fields to NULL
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

        # Step 2: Update packagemanagement to set dest_lat and dest_lng to NULL where they match
        # Assuming that destination_lat and destination_lng in packagemanagement
        # are directly associated with the DDT being deleted.
        # This part of the code implicitly assumes that the latitude and longitude
        # values stored in the `ddts` table for a specific DDT name are used as
        # `destination_lat` and `destination_lng` in the `packagemanagement` table.
        # It's generally safer to establish a foreign key relationship if possible.
        
        # Get latitude and longitude from the DDT being deleted
        cur.execute("SELECT latitude, longitude FROM ddts WHERE id = %s", (ddt_id,))
        coord_result = cur.fetchone()
        
        if coord_result:
            latitude_to_null, longitude_to_null = coord_result
            cur.execute("""
                UPDATE packagemanagement
                SET destination_lat = NULL, destination_lng = NULL
                WHERE destination_lat = %s AND destination_lng = %s
            """, (latitude_to_null, longitude_to_null))
            app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Related packagemanagement entries updated to NULL based on coordinates.")
        else:
            app.logger.warning(f"[DEBUG][DELETE DDT ID: {ddt_id}] No coordinates found for DDT '{ddt_name}', skipping packagemanagement update by coords.")


        # Step 3: Update users_data to set assigned_ddt to NULL where it matches the deleted DDT's name
                # Step 4: Delete from ddts table
        cur.execute("DELETE FROM ddts WHERE id = %s RETURNING id", (ddt_id,))
        deleted_id_tuple = cur.fetchone()
        app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Result from DB after DELETE (fetchone): {deleted_id_tuple}")

        if deleted_id_tuple:
            conn.commit()
            app.logger.info(f"[DEBUG][DELETE DDT ID: {ddt_id}] Delete committed.")
            return jsonify({'message': f'DDT {ddt_id} deleted and related entries updated successfully'}), 200
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


# Update the update_warehouse function to handle latitude and longitude AND update users_data
@app.route('/update_warehouse/<int:warehouse_id>', methods=['PUT'])
def update_warehouse(warehouse_id):
    data = request.json
    app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Received data: {data}")
    
    new_name = data.get('name')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if new_name is None and latitude is None and longitude is None:
        app.logger.warning(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] No data provided for update.")
        return jsonify({'error': 'No data provided for update'}), 400

    update_fields = []
    update_values = []
    
    if new_name is not None:
        update_fields.append("name = %s")
        update_values.append(new_name)
    if latitude is not None:
        try:
            lat_float = float(latitude)
            update_fields.append("latitude = %s")
            update_values.append(lat_float)
        except ValueError:
            app.logger.error(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Invalid latitude value: {latitude}")
            return jsonify({'error': 'Invalid latitude value. Must be a number.'}), 400
    if longitude is not None:
        try:
            lng_float = float(longitude)
            update_fields.append("longitude = %s")
            update_values.append(lng_float)
        except ValueError:
            app.logger.error(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Invalid longitude value: {longitude}")
            return jsonify({'error': 'Invalid longitude value. Must be a number.'}), 400
            
    if not update_fields:
        app.logger.warning(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] No valid fields to update after processing.")
        return jsonify({'error': 'No valid fields to update'}), 400
        
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

        update_values.append(warehouse_id)
        sql_update_warehouse = f"UPDATE warehouses SET {', '.join(update_fields)} WHERE id = %s RETURNING id, name, latitude, longitude"
        app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] SQL (warehouses): {sql_update_warehouse} Data: {tuple(update_values)}")
        cur.execute(sql_update_warehouse, tuple(update_values))
        updated_warehouse_record = cur.fetchone()
        app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] DB Result (warehouses): {updated_warehouse_record}")

        if updated_warehouse_record:
            if new_name is not None and old_warehouse_name != new_name:
                # Update droneassignment table (the 'name' column refers to the warehouse name)
                sql_update_droneassignment = "UPDATE droneassignment SET name = %s WHERE name = %s"
                app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] SQL (droneassignment): {sql_update_droneassignment} Data: {(new_name, old_warehouse_name)}")
                cur.execute(sql_update_droneassignment, (new_name, old_warehouse_name))
                app.logger.info(f"[DEBUG][UPDATE WAREHOUSE ID: {warehouse_id}] Updated droneassignment table. {cur.rowcount} rows affected.")
                
                # Update packagemanagement table as well
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

# Update the delete_warehouse function to set packagemanagement warehouse_name to NULL
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

        # Update packagemanagement entries to set warehouse_name to NULL
        try:
            sql_update_packages = "UPDATE packagemanagement SET warehouse_name = NULL WHERE warehouse_name = %s"
            app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] SQL (packagemanagement): {sql_update_packages} Data: {warehouse_name_to_delete}")
            cur.execute(sql_update_packages, (warehouse_name_to_delete,))
            app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Updated {cur.rowcount} packages in packagemanagement table.")
        except psycopg2.Error as pm_error:
            app.logger.warning(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Could not update packagemanagement (may not exist or schema mismatch): {pm_error}")

        # Update users_data to set assigned_warehouse to NULL where it matches the deleted warehouse's name
        
        # Delete the warehouse
        cur.execute("DELETE FROM warehouses WHERE id = %s RETURNING id", (warehouse_id,))
        deleted_id_tuple = cur.fetchone() 
        app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] DB Result (warehouses): {deleted_id_tuple}")
        
        if deleted_id_tuple: 
            conn.commit()
            app.logger.info(f"[DEBUG][DELETE WAREHOUSE ID: {warehouse_id}] Committed.")
            return jsonify({'message': f'Warehouse {warehouse_id} ({warehouse_name_to_delete}) deleted and related entries updated successfully'}), 200
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

########################################### DRONE ASSIGNMENT #########################################

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
    app.logger.info("Starting Flask application on http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)