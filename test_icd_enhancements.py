import sys
from icd_api_service import search_icd_codes, get_entity, get_icd_chapters

# These would be the secure credentials
CLIENT_ID = "86320238-677b-494c-a47c-2079517c081d_0235ecaa-3c40-4f04-bc05-95d8cf548270"
CLIENT_SECRET = "E4YgTAfelAHlIb9yxrVsKuWBRVVoVjFiPlkEbHIkgGs="

def run_tests():
    print("--- Testing search_icd_codes ---")
    search_results, search_status = search_icd_codes(
        "Diabetes mellitus",
        client_id_override=CLIENT_ID,
        client_secret_override=CLIENT_SECRET
    )
    print(f"Search status: {search_status}")
    if search_status in ["SUCCESS", "SUCCESS_FROM_CACHE"] and search_results:
        print(f"Found {len(search_results)} results for 'Diabetes mellitus'. First result: {search_results[0]}")
    elif search_results is None:
        print("Search returned None results.")
    else:
        print("Search returned no results or failed.")

    print("\n--- Testing get_entity ---")
    # Example entity URI (e.g., first result from a successful search, or a known chapter URI)
    # Using a known chapter URI for ICD-11 MMS 2023-01 (Chapter 1)
    # From previous exploration, a chapter URI might look like http://id.who.int/icd/entity/CHAPTER_ID_HERE
    # The WHO browser for 2023-01 release (https://icd.who.int/browse11/l-m/en/http%3A%2F%2Fid.who.int%2Ficd%2Frelease%2F11%2F2023-01%2Fmms)
    # shows Chapter 1 as "Certain infectious or parasitic diseases"
    # Let's try to get the release root first to find a chapter URI

    release_uri_for_chapters = "https://id.who.int/icd/release/11/2023-01/mms"
    print(f"Fetching release entity: {release_uri_for_chapters} to get a sample chapter URI...")
    release_entity_data, release_entity_status = get_entity(
        release_uri_for_chapters,
        client_id_override=CLIENT_ID,
        client_secret_override=CLIENT_SECRET
    )

    sample_chapter_uri = None
    if release_entity_status == "SUCCESS" and release_entity_data and release_entity_data.get('child'):
        sample_chapter_uri = release_entity_data['child'][0] # Take the first child URI
        print(f"Found sample chapter URI from release root: {sample_chapter_uri}")
    else:
        print(f"Could not fetch children from release URI {release_uri_for_chapters}. Status: {release_entity_status}")
        # Fallback URI if above fails, this is Chapter 1 for some versions, might not be stable.
        # This URI is from the foundation component, not a specific release, so it might differ.
        # sample_chapter_uri = "http://id.who.int/icd/entity/1435254666"
        # print(f"Using a known foundation chapter URI as fallback: {sample_chapter_uri}")


    if sample_chapter_uri:
        entity_data, entity_status = get_entity(
            sample_chapter_uri,
            client_id_override=CLIENT_ID,
            client_secret_override=CLIENT_SECRET
        )
        print(f"get_entity status for {sample_chapter_uri}: {entity_status}")
        if entity_status == "SUCCESS" and entity_data:
            print(f"Entity Title: {entity_data.get('title', {}).get('@value', 'N/A')}, ClassKind: {entity_data.get('classKind', 'N/A')}")
    else:
        print("Skipping get_entity test as no sample chapter URI was obtained.")


    print("\n--- Testing get_icd_chapters ---")
    # Using the 2023-01 MMS release URI
    chapters_data, chapters_status = get_icd_chapters(
        release_uri_for_chapters, # Defined above
        client_id_override=CLIENT_ID,
        client_secret_override=CLIENT_SECRET
    )
    print(f"get_icd_chapters status: {chapters_status}")
    if chapters_status == "SUCCESS" and chapters_data:
        print(f"Found {len(chapters_data)} chapters. First 3 chapters:")
        for i, chapter in enumerate(chapters_data[:3]):
            title_obj = chapter.get('title', {})
            title_val = title_obj.get('@value', 'N/A')
            lang = title_obj.get('@language', 'N/A')
            print(f"  Chapter {i+1}: ID: {chapter.get('id')}, Title: {title_val} ({lang}), ClassKind: {chapter.get('classKind')}")
    elif chapters_data is None:
         print("get_icd_chapters returned None for chapters list.")
    else:
        print("get_icd_chapters returned no chapters or failed.")

if __name__ == "__main__":
    run_tests()
