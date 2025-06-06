import sys
import os
import json # For checking icd_data.json structure if needed, and for parse_icd_json

# Adjust Python path to include the project root directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

try:
    from index import app, db # Assuming app and db are directly in index.py
    from models import Paciente, Diagnostico # Paciente just to ensure models are loaded
    from process_local_icd import parse_icd_json, extract_diagnostico_data
except ImportError as e:
    print(f"Error importing application modules: {e}")
    print("Please ensure that index.py and models.py are in the project root")
    print("and process_local_icd.py is also in the project root.")
    sys.exit(1)

# Define the expected path for the user-provided ICD data file
USER_ICD_DATA_FILE = os.path.join(project_root, "icd_data.json")

def populate_diagnosticos():
    """
    Populates the Diagnostico table in the database using data
    from USER_ICD_DATA_FILE.
    """
    print(f"Starting diagnostico population from: {USER_ICD_DATA_FILE}")

    if not os.path.exists(USER_ICD_DATA_FILE):
        print(f"Error: Source ICD data file not found: {USER_ICD_DATA_FILE}")
        print("This script requires a user-provided 'icd_data.json' in the project root.")
        return

    # Step 1: Parse the raw ICD data from the user-provided file
    # parse_icd_json expects a JSON file containing a list of strings.
    print(f"Parsing {USER_ICD_DATA_FILE}...")
    raw_parsed_data = parse_icd_json(USER_ICD_DATA_FILE)
    if raw_parsed_data is None:
        print("Failed to parse ICD data. Aborting.")
        return

    # Step 2: Extract diagnostico-specific data (code, description)
    print("Extracting diagnostico entries...")
    diagnostico_list_from_file = extract_diagnostico_data(raw_parsed_data)
    if not diagnostico_list_from_file:
        print("No diagnostico entries extracted from the file. Aborting.")
        return

    print(f"Found {len(diagnostico_list_from_file)} entries in the source file.")

    # Step 3: Fetch existing diagnosticos from DB
    print("Fetching existing diagnosticos from the database...")
    try:
        existing_diagnosticos_db = Diagnostico.query.all()
        existing_diagnosticos_map = {d.codigo: d for d in existing_diagnosticos_db}
        print(f"Found {len(existing_diagnosticos_map)} existing diagnosticos in the database.")
    except Exception as e:
        print(f"Error fetching existing diagnosticos from database: {e}")
        return

    added_count = 0
    updated_count = 0

    # Step 4: Iterate and update/add
    print("Processing and syncing diagnostico entries...")
    for item in diagnostico_list_from_file:
        code = item.get('codigo')
        desc = item.get('descripcion')

        if not code or not desc:
            print(f"Skipping item with missing code or description: {item}")
            continue

        if code in existing_diagnosticos_map:
            # Existing entry: update if description changed
            existing_record = existing_diagnosticos_map[code]
            if existing_record.descripcion != desc:
                existing_record.descripcion = desc
                updated_count += 1
        else:
            # New entry: create and add
            new_diag = Diagnostico(codigo=code, descripcion=desc)
            db.session.add(new_diag)
            added_count += 1

    # Step 5: Commit changes
    if added_count > 0 or updated_count > 0:
        print(f"Committing changes to database: {added_count} added, {updated_count} updated.")
        try:
            db.session.commit()
            print("Database commit successful.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing to database: {e}")
            print("Database changes have been rolled back.")
            return
    else:
        print("No new or updated diagnosticos to commit.")

    print(f"Population summary: {added_count} added, {updated_count} updated.")
    print("Diagnostico population process finished.")
    print(f"DEBUG: Final summary - Added: {added_count}, Updated: {updated_count}.")

if __name__ == "__main__":
    print("--- Starting Diagnostico Database Population Script ---")

    # Ensure USER_ICD_DATA_FILE exists before trying to use app context
    # (as populate_diagnosticos also checks this, but good to check early)
    if not os.path.exists(USER_ICD_DATA_FILE):
        print(f"Critical Error: Source ICD data file '{USER_ICD_DATA_FILE}' not found.")
        print("Please ensure this file exists in the project root directory.")
        sys.exit(1)

    # Create Flask app and push an app context
    # Assuming 'app' is imported directly and configured from index.py
    if 'app' not in globals():
        print("Flask 'app' instance not found. Ensure it's imported correctly.")
        sys.exit(1)

    with app.app_context():
        print("Flask application context pushed.")
        # Optional: Initialize DB if it's not done automatically on app context for scripts
        db.create_all() # Usually not needed if app is set up for this,
                          # and can be dangerous if migrations are used.
                          # Assuming tables already exist.
        populate_diagnosticos()

    print("--- Diagnostico Database Population Script Finished ---")
