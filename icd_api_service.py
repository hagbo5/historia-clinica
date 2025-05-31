import requests
import os
import time
import json # Though requests.json() is often enough

# --- Configuration ---
TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
SEARCH_URL_BASE = "https://id.who.int/icd/release/11/2023-01/mms/search" # ICD-11

# --- In-memory cache for the token ---
_cached_token = None
_token_expiry_time = 0 # Unix timestamp when the token expires
TOKEN_VALIDITY_SECONDS = 3600 # Typically 1 hour, as per OAuth standards
TOKEN_EXPIRY_BUFFER = 60 # Request new token 60 seconds before it actually expires

def get_icd_api_token(): # Removed override parameters
    global _cached_token, _token_expiry_time

    # Always check cache first.
    if _cached_token and time.time() < _token_expiry_time:
        # print("Using cached token")
        return (_cached_token, "SUCCESS_FROM_CACHE") # Ensure tuple is returned

    # print("Requesting new token...")
    # Directly use environment variables
    client_id = os.environ.get("ICD_API_CLIENT_ID")
    client_secret = os.environ.get("ICD_API_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: ICD_API_CLIENT_ID or ICD_API_CLIENT_SECRET not found in environment variables.")
        return (None, "MISSING_CREDENTIALS")

    payload = {
        "client_id": client_id, # Uses os.environ.get() result
        "client_secret": client_secret, # Uses os.environ.get() result
        "grant_type": "client_credentials",
        "scope": "icdapi_access"
    }

    try:
        response = requests.post(TOKEN_URL, data=payload, timeout=10) # Added timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        
        token_data = response.json()
        _cached_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", TOKEN_VALIDITY_SECONDS) # Use provided or default
        _token_expiry_time = time.time() + expires_in - TOKEN_EXPIRY_BUFFER
        
        # print(f"New token obtained, expires in approx {expires_in // 60} minutes.") # For debugging
        return (_cached_token, "SUCCESS")
        
    except requests.exceptions.RequestException as e:
        print(f"Error requesting ICD API token: {e}")
        _cached_token = None # Clear cache on error
        _token_expiry_time = 0
        return (None, "TOKEN_REQUEST_FAILED")
    except json.JSONDecodeError:
        print("Error: Could not decode JSON response from token endpoint.")
        _cached_token = None
        _token_expiry_time = 0
        return (None, "TOKEN_REQUEST_FAILED") # Group JSONDecodeError with token request failures


def search_icd_codes(search_term): # Removed override parameters
    token, token_status = get_icd_api_token() # Call without overrides
    # Also handle "SUCCESS_FROM_CACHE" as a success
    if token_status not in ["SUCCESS", "SUCCESS_FROM_CACHE"]:
        print(f"Error: Could not retrieve API token for ICD search. Status: {token_status}")
        return (None, token_status) # Propagate the error status

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": "es", # As per user's example
        "API-Version": "v2" # Added API-Version header
    }
    params = {
        "q": search_term,
        # "useFlexisearch": "true" # Might be useful for more flexible search
    }

    try:
        response = requests.get(SEARCH_URL_BASE, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        results = response.json()
        
        # Transform results into the desired format: list of {'id': ..., 'label': ...}
        # Based on user example: item["title"]["@value"], item["id"]
        # item["id"] is often a URI like "http://id.who.int/icd/entity/XXXXXXXXX"
        # This URI can be used as the unique code.
        
        formatted_results = []
        if results and "destinationEntities" in results and isinstance(results["destinationEntities"], list):
            for item in results["destinationEntities"]:
                title_info = item.get("title", "No title available") # Default to string if title is missing
                if isinstance(title_info, dict):
                    label = title_info.get("@value", "No title available")
                elif isinstance(title_info, str):
                    label = title_info # Use the string directly
                else:
                    label = "No title available" # Fallback for unexpected types

                entity_id = item.get("id", None) # This is the URI
                
                if entity_id: # Only include if there's an ID
                    formatted_results.append({
                        "id": entity_id,  # This will be the "code" we store
                        "label": label,
                        "raw_title": item.get("title"), # For context if needed
                        "raw_id": item.get("id")
                    })
        return (formatted_results, "SUCCESS")

    except requests.exceptions.RequestException as e:
        print(f"Error searching ICD codes for '{search_term}': {e}")
        return (None, "SEARCH_API_ERROR")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from ICD search for '{search_term}'.")
        return (None, "SEARCH_API_ERROR") # Group JSONDecodeError with search API errors


def get_entity(entity_uri): # Removed override parameters
    token, token_status = get_icd_api_token() # Call without overrides

    if token_status not in ["SUCCESS", "SUCCESS_FROM_CACHE"]:
        print(f"Error: Could not retrieve API token for get_entity({entity_uri}). Status: {token_status}")
        return (None, token_status)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": "es", # Or make this a parameter if needed
        "API-Version": "v2"
    }

    try:
        response = requests.get(entity_uri, headers=headers, timeout=15)
        response.raise_for_status()
        return (response.json(), "SUCCESS")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching entity {entity_uri}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}, content: {e.response.text[:200]}")
        return (None, "ENTITY_REQUEST_FAILED")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for entity {entity_uri}: {e}")
        return (None, "JSON_DECODE_ERROR")


def get_icd_chapters(release_uri): # Removed override parameters
    chapters_list = []

    # Get the main release entity
    release_data, status = get_entity(release_uri) # Call without overrides

    if status != "SUCCESS":
        print(f"Error fetching release URI {release_uri}. Status: {status}")
        return (None, status)

    if not release_data or 'child' not in release_data:
        print(f"No 'child' property found in release data for {release_uri}.")
        return (None, "NO_CHAPTERS_FOUND_IN_RELEASE_DATA")

    chapter_uris = release_data.get('child', [])
    print(f"Found {len(chapter_uris)} potential chapter URIs in {release_uri}.")

    for i, chapter_uri in enumerate(chapter_uris): # Process all chapters
        print(f"Fetching details for chapter URI ({i+1}/{len(chapter_uris)}): {chapter_uri}")
        chapter_data, chapter_status = get_entity(chapter_uri) # Call without overrides
        if chapter_status == "SUCCESS" and chapter_data:
            chapters_list.append({
                "id": chapter_data.get('@id', chapter_uri),
                "title": chapter_data.get('title', {}), # Keep the title object
                "classKind": chapter_data.get('classKind', 'N/A')
            })
        else:
            print(f"Warning: Could not fetch details for chapter {chapter_uri}. Status: {chapter_status}")
            # Optionally, add placeholder or error info to the list
            chapters_list.append({
                "id": chapter_uri,
                "title": {"@value": "Error fetching title"},
                "error_status": chapter_status
            })

    return (chapters_list, "SUCCESS")


if __name__ == '__main__':
    # Example usage (for testing the service directly)
    # Ensure ICD_API_CLIENT_ID and ICD_API_CLIENT_SECRET are set in your environment
    print("Attempting to get a token...")
    test_token = get_icd_api_token()
    if test_token:
        print(f"Successfully got a token (first few chars): {test_token[:10]}...")
        
        print("\nSearching for 'diabetes'...")
        diabetes_results = search_icd_codes("diabetes")
        if diabetes_results:
            print(f"Found {len(diabetes_results)} results for 'diabetes':")
            for res in diabetes_results[:5]: # Print first 5
                print(f"  ID: {res['id']}, Label: {res['label']}")
        else:
            print("No results for 'diabetes' or error occurred.")

        print("\nSearching for 'gripe'...")
        gripe_results = search_icd_codes("gripe") # Common cold/flu
        if gripe_results:
            print(f"Found {len(gripe_results)} results for 'gripe':")
            for res in gripe_results[:5]:
                print(f"  ID: {res['id']}, Label: {res['label']}")
        else:
            print("No results for 'gripe' or error occurred.")
            
        # Test token caching (call again)
        print("\nAttempting to get a token again (should be cached)...")
        test_token_2 = get_icd_api_token()
        if test_token_2:
            print(f"Successfully got a token (first few chars): {test_token_2[:10]}...")
            if test_token == test_token_2:
                print("Token was successfully retrieved from cache.")
            else:
                print("Token was re-fetched (unexpected for cache test).")

    else:
        print("Failed to get a token. Ensure environment variables are set.")
