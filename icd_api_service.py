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

def get_icd_api_token():
    global _cached_token, _token_expiry_time

    # Check cache first
    if _cached_token and time.time() < _token_expiry_time:
        # print("Using cached token") # For debugging
        return _cached_token

    # print("Requesting new token...") # For debugging
    client_id = os.environ.get("ICD_API_CLIENT_ID")
    client_secret = os.environ.get("ICD_API_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: ICD_API_CLIENT_ID or ICD_API_CLIENT_SECRET not found in environment variables.")
        return (None, "MISSING_CREDENTIALS")

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
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


def search_icd_codes(search_term):
    token, token_status = get_icd_api_token()
    if token_status != "SUCCESS":
        print(f"Error: Could not retrieve API token for ICD search. Status: {token_status}")
        return (None, token_status) # Propagate the error status

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": "es" # As per user's example
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
                title_info = item.get("title", {})
                label = title_info.get("@value", "No title available")
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
