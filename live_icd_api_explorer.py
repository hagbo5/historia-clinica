import os
import sys
import requests
# Assuming icd_api_service.py is in the same directory or Python path
from icd_api_service import get_icd_api_token, search_icd_codes

def print_entity_summary(entity_data, indent="  "):
    if not entity_data or not isinstance(entity_data, dict):
        print(f"{indent}Invalid or empty entity data.")
        return

    title = entity_data.get('title', {}).get('@value', 'N/A')
    entity_id = entity_data.get('@id', 'N/A')
    class_kind = entity_data.get('classKind', 'N/A')
    is_leaf = entity_data.get('isLeaf', False) # Default to False if not present
    children = entity_data.get('child', [])
    parent_uris = entity_data.get('parent', [])

    print(f"{indent}URI: {entity_id}")
    print(f"{indent}Title: {title}")
    print(f"{indent}ClassKind: {class_kind}")
    print(f"{indent}IsLeaf: {is_leaf}")
    print(f"{indent}Parent URIs: {len(parent_uris)} ({parent_uris[:2]}...)") # Show first few
    print(f"{indent}Child URIs: {len(children)} ({children[:2]}...)") # Show first few
    return children

def explore_live_api(client_id_arg, client_secret_arg):
    print(f"Attempting to use provided Client ID (length: {len(client_id_arg)}) and Secret (length: {len(client_secret_arg)}) for token retrieval.")

    print("\n--- Phase 1: Token Retrieval ---")
    token, token_status = get_icd_api_token(
        client_id_override=client_id_arg,
        client_secret_override=client_secret_arg
    )

    if token_status in ["SUCCESS", "SUCCESS_FROM_CACHE"]: # SUCCESS_FROM_CACHE unlikely if overrides used, but good to include
        print(f"Token retrieval: SUCCESSFUL (Status: {token_status}).")
        # DO NOT PRINT THE TOKEN ITSELF
    else:
        print(f"Token retrieval: FAILED. Status: {token_status}")
        print("Cannot proceed with API exploration without a valid token.")
        return

    print("\n--- Phase 2: Live API Exploration ---")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": "en", # Using English for this exploration
        "API-Version": "v2"
    }

    # 1. Fetch Foundation Root Entity
    foundation_root_uri = "http://id.who.int/icd/entity"
    print(f"\nFetching Foundation Root: {foundation_root_uri}")
    all_chapter_uris = []
    try:
        response_root = requests.get(foundation_root_uri, headers=headers, timeout=30)
        response_root.raise_for_status()
        root_data = response_root.json()
        print(f"Successfully fetched Foundation Root. Status: {response_root.status_code}")
        print_entity_summary(root_data, indent="  ")
        all_chapter_uris = root_data.get('child', [])
        if not all_chapter_uris:
            print("  No children found for the foundation root. This is unexpected if it's the entry point for chapters.")
        else:
            print(f"  Found {len(all_chapter_uris)} top-level children (expected to be chapters).")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Foundation Root {foundation_root_uri}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response content (first 300 chars): {e.response.text[:300]}")
        print("Cannot proceed if foundation root (chapters list) cannot be fetched.")
        return # Stop if we can't get chapters

    # 2. Fetch details for the first few chapters
    if all_chapter_uris:
        print(f"\nFetching details for the first few chapters (up to 3):")
        chapters_to_explore_children_of = []
        for i, chapter_uri in enumerate(all_chapter_uris[:3]):
            print(f"\n  Fetching Chapter: {chapter_uri}")
            try:
                response_chapter = requests.get(chapter_uri, headers=headers, timeout=20)
                response_chapter.raise_for_status()
                chapter_data = response_chapter.json()
                print(f"  Successfully fetched Chapter. Status: {response_chapter.status_code}")
                children_of_chapter = print_entity_summary(chapter_data, indent="    ")
                if children_of_chapter: # If this chapter has children
                    chapters_to_explore_children_of.append(chapter_data)
            except requests.exceptions.RequestException as e_chapter:
                print(f"  Error fetching chapter {chapter_uri}: {e_chapter}")
                if hasattr(e_chapter, 'response') and e_chapter.response is not None:
                    print(f"  Response status: {e_chapter.response.status_code}")
                    print(f"  Response content (first 300 chars): {e_chapter.response.text[:300]}")

        # 3. Fetch details for children of the first successfully explored chapter
        if chapters_to_explore_children_of:
            first_chapter_data = chapters_to_explore_children_of[0]
            first_chapter_title = first_chapter_data.get('title', {}).get('@value', 'N/A')
            first_chapter_children_uris = first_chapter_data.get('child', [])

            print(f"\nFetching children for the first explored chapter: '{first_chapter_title}' (URI: {first_chapter_data.get('@id')})")
            if first_chapter_children_uris:
                print(f"  Chapter '{first_chapter_title}' has {len(first_chapter_children_uris)} children. Fetching details for first few (up to 3):")
                for i, sub_entity_uri in enumerate(first_chapter_children_uris[:3]):
                    print(f"\n    Fetching Sub-entity: {sub_entity_uri}")
                    try:
                        response_sub_entity = requests.get(sub_entity_uri, headers=headers, timeout=15)
                        response_sub_entity.raise_for_status()
                        sub_entity_data = response_sub_entity.json()
                        print(f"    Successfully fetched Sub-entity. Status: {response_sub_entity.status_code}")
                        print_entity_summary(sub_entity_data, indent="      ")
                    except requests.exceptions.RequestException as e_sub_entity:
                        print(f"    Error fetching sub-entity {sub_entity_uri}: {e_sub_entity}")
                        if hasattr(e_sub_entity, 'response') and e_sub_entity.response is not None:
                            print(f"    Response status: {e_sub_entity.response.status_code}")
                            print(f"    Response content (first 300 chars): {e_sub_entity.response.text[:300]}")
            else:
                print(f"  Chapter '{first_chapter_title}' has no children listed.")
        else:
            print("\nNo chapters successfully explored to show their children.")
    else:
        print("\nNo chapter URIs found from root, cannot explore chapters.")

    # 4. Optional: Cross-check with search
    print("\n--- Phase 3: Search Functionality Cross-Check ---")
    search_term_example = "Diabetes mellitus" # A common term
    print(f"Attempting search for '{search_term_example}' with direct credentials...")
    results, search_status = search_icd_codes(
        search_term_example,
        client_id_override=client_id_arg,
        client_secret_override=client_secret_arg
    )
    if search_status in ["SUCCESS", "SUCCESS_FROM_CACHE"]:
        print(f"Search for '{search_term_example}': SUCCESSFUL. Found {len(results) if results else 0} items.")
        if results:
            print(f"  Details of first search result:")
            first_result_uri = results[0].get('id')
            if first_result_uri:
                print(f"    Fetching entity details for search result URI: {first_result_uri}")
                try:
                    response_search_entity = requests.get(first_result_uri, headers=headers, timeout=15)
                    response_search_entity.raise_for_status()
                    search_entity_data = response_search_entity.json()
                    print(f"    Successfully fetched entity from search. Status: {response_search_entity.status_code}")
                    print_entity_summary(search_entity_data, indent="      ")
                except requests.exceptions.RequestException as e_search_entity:
                    print(f"    Error fetching entity from search {first_result_uri}: {e_search_entity}")
            else:
                print("    First search result had no URI ('id').")
    else:
        print(f"Search for '{search_term_example}': FAILED. Status: {search_status}")

    print("\n--- Live API Exploration Finished ---")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        cid = sys.argv[1]
        csecret = sys.argv[2]
        explore_live_api(cid, csecret)
    else:
        print("Usage: python live_icd_api_explorer.py <CLIENT_ID> <CLIENT_SECRET>")
        print("Please provide Client ID and Client Secret as command-line arguments.")
