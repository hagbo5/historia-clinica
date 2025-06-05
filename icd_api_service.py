import json

# Import local services
try:
    from local_icd_service import (
        get_chapters as local_get_chapters,
        get_disease_details as local_get_disease_details,
        search_diseases as local_search_diseases
    )
except ImportError:
    print("Error: Could not import from local_icd_service. Make sure it's in the Python path.")
    # Define dummy functions to allow script to load for inspection if local_icd_service is missing
    def local_get_chapters(): return []
    def local_get_disease_details(_code): return None
    def local_search_diseases(_term): return []

# --- Configuration & Token Logic (Commented out or Removed) ---

def search_icd_codes(search_term):
    """
    Searches ICD codes using the local_icd_service.
    Transforms results to the format: list of {'id': disease_code, 'label': disease_name}.
    """
    # print(f"icd_api_service.search_icd_codes searching for: {search_term}")

    # Call local_search_diseases from local_icd_service
    # This returns: [{'code': ..., 'name': ..., 'description': ..., 'inclusions': ...}, ...]
    local_results = local_search_diseases(search_term)

    if local_results is None: # Should be an empty list if no results, None if error in local_search_diseases
        print(f"Error or no data from local_search_diseases for '{search_term}'.")
        return ([], "LOCAL_SEARCH_ERROR_OR_NO_DATA")

    formatted_results = []
    for disease in local_results:
        formatted_results.append({
            "id": disease.get("code"),    # Use disease code as 'id'
            "label": disease.get("name")  # Use disease name as 'label'
            # "raw_title": disease.get("name"), # Optional: if more detail was needed
            # "raw_id": disease.get("code")
        })

    # print(f"Formatted results for '{search_term}': {formatted_results[:3]}") # Debug: first 3 results
    return (formatted_results, "SUCCESS")


def get_entity(entity_code): # Parameter changed from entity_uri
    """
    Retrieves entity details from local_icd_service using the disease code.
    """
    # print(f"icd_api_service.get_entity fetching details for code: {entity_code}")
    disease_details = local_get_disease_details(entity_code)

    if disease_details:
        # The returned structure is {'code': ..., 'name': ..., 'description': ..., 'inclusions': ...}
        # This is returned directly. The calling code might need adaptation if it
        # expected the exact WHO API structure.
        return (disease_details, "SUCCESS")
    else:
        return (None, "NOT_FOUND_LOCAL")


def get_icd_chapters():
    """
    Retrieves chapter list from local_icd_service.
    Transforms data to: [{'id': 'local_chapter_XX', 'title': {'@value': 'Chapter Title'}}, ...]
    """
    # print("icd_api_service.get_icd_chapters called")
    local_chapters = local_get_chapters() # Returns [{'chapter_id': '01', 'chapter_title': 'Title'}]

    if local_chapters is None: # Should be an empty list if no chapters, None if error
        print("Error or no data from local_get_chapters.")
        return ([], "LOCAL_CHAPTERS_ERROR_OR_NO_DATA")
        
    transformed_chapters = []
    for chapter in local_chapters:
        chapter_id_str = chapter.get("chapter_id", "unknown")
        transformed_chapters.append({
            "id": f"local_chapter_{chapter_id_str}", # Construct a unique ID
            "title": {
                "@value": chapter.get("chapter_title", "No Title")
            },
            # "classKind": "Chapter" # Add if necessary for compatibility
        })

    # print(f"Transformed chapters: {transformed_chapters[:2]}") # Debug: first 2 chapters
    return (transformed_chapters, "SUCCESS")


if __name__ == '__main__':
    print("--- Testing icd_api_service.py with Local Data ---")
    # Note: This test block assumes 'structured_icd_data.json' exists and is readable
    # by local_icd_service.py. Run process_local_icd.py if needed.

    # Test 1: Search for codes
    print("\n1. Searching for 'Cholera'...")
    search_results, status = search_icd_codes("Cholera")
    if status == "SUCCESS":
        print(f"Found {len(search_results)} results for 'Cholera':")
        for res in search_results[:5]: # Print first 5
            print(f"  ID: {res.get('id')}, Label: {res.get('label')}")
    else:
        print(f"Search failed or no results. Status: {status}")

    print("\n   Searching for 'Diabetes'...")
    search_results_diabetes, status_diabetes = search_icd_codes("Diabetes")
    if status_diabetes == "SUCCESS":
        print(f"Found {len(search_results_diabetes)} results for 'Diabetes':")
        for res in search_results_diabetes[:3]:
            print(f"  ID: {res.get('id')}, Label: {res.get('label')}")
    else:
        print(f"Search for 'Diabetes' failed. Status: {status_diabetes}")


    # Test 2: Get entity details
    print("\n2. Getting details for entity code '1A00' (Cholera)...") # Example code
    entity_details, status = get_entity("1A00")
    if status == "SUCCESS" and entity_details:
        print(f"Details for '1A00':")
        print(f"  Code: {entity_details.get('code')}")
        print(f"  Name: {entity_details.get('name')}")
        print(f"  Description (first 100 chars): {entity_details.get('description', '')[:100]}...")
        print(f"  Inclusions: {entity_details.get('inclusions')}")
    else:
        print(f"Could not get details for '1A00'. Status: {status}")

    print("\n   Getting details for non-existent code 'XXXX'...")
    non_existent_entity, status_ne = get_entity("XXXX")
    if status_ne == "NOT_FOUND_LOCAL" and non_existent_entity is None:
        print("Correctly handled non-existent entity 'XXXX'.")
    else:
        print(f"Error or unexpected result for non-existent entity. Status: {status_ne}, Details: {non_existent_entity}")


    # Test 3: Get ICD Chapters
    print("\n3. Getting ICD Chapters...")
    chapters, status = get_icd_chapters()
    if status == "SUCCESS":
        print(f"Found {len(chapters)} chapters:")
        for chapter in chapters[:3]: # Print first 3
            print(f"  ID: {chapter.get('id')}, Title: {chapter.get('title', {}).get('@value')}")
    else:
        print(f"Could not retrieve chapters. Status: {status}")

    print("\n--- End of Local Data Tests ---")

    # To run these tests, ensure:
    # 1. `local_icd_service.py` is in the same directory or Python path.
    # 2. `structured_icd_data.json` exists in the location expected by `local_icd_service.py`
    #    (usually project root, generated by `process_local_icd.py`).
    #    Run `python process_local_icd.py` if this file is missing or outdated.
    #
    # Example:
    # python process_local_icd.py
    # python icd_api_service.py
    #
    # If local_icd_service itself needs a Flask app context for any of its operations
    # (not typically for file-based loading but good to be aware of), this test block
    # might need to be wrapped in `with app.app_context():`.
    # However, `local_icd_service.py` as defined earlier primarily loads from a JSON file
    # and does not require an app context for its core functions.
