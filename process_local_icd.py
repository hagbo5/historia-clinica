import json
import re

def parse_icd_json(file_path="icd_data.json"):
    """
    Parses ICD data from a JSON file (expected to be a list of strings)
    and transforms it into a structured Python dictionary.
    """
    try:
        with open(file_path, 'r') as f:
            raw_data = json.load(f)
        print(f"DEBUG: Successfully read {len(raw_data)} lines/items from {file_path}.")
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {file_path}")
        return None

    chapters_data = []
    current_chapter = None
    current_disease = None

    chapter_re = re.compile(r"^Chapter ([IVXLCDM]+)")
    disease_re = re.compile(r"^([A-Z0-9]{3,8}(?:\.[0-9A-Z]+)?)\s+(.+)")
    inclusions_re = re.compile(r"^Inclusions:(.*)")
    inclusion_item_re = re.compile(r"^\s*[-•*]\s*(.+)")

    roman_map = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    def roman_to_int(s):
        total = 0
        prev_value = 0
        for char in reversed(s):
            value = roman_map[char]
            if value < prev_value:
                total -= value
            else:
                total += value
            prev_value = value
        return total

    for item in raw_data:
        if item is None:
            continue
        line = item.strip()
        if not line:
            continue

        chapter_match = chapter_re.match(line)
        if chapter_match:
            roman_numeral = chapter_match.group(1)
            chapter_id_int = roman_to_int(roman_numeral)
            chapter_id_str = f"{chapter_id_int:02}"
            chapter_title_candidate = line[len(chapter_match.group(0)):].strip()

            if current_chapter and current_disease:
                current_chapter["diseases"].append(current_disease)
                current_disease = None
            if current_chapter:
                 chapters_data.append(current_chapter)

            current_chapter = {
                "chapter_id": chapter_id_str,
                "chapter_title": chapter_title_candidate,
                "diseases": []
            }
            current_disease = None
            continue

        disease_match = disease_re.match(line)
        if disease_match:
            if current_chapter is None:
                # This case should ideally not happen if chapters always precede diseases
                # Or if the chapter title logic is robust.
                # If it does, we might need to create a default chapter or log an error.
                # For now, assume current_chapter is always set if disease_match occurs after a chapter line.
                pass # Error or default chapter handling can be added if necessary

            if current_disease: # Save previous disease
                if current_chapter: # Ensure chapter exists
                    current_chapter["diseases"].append(current_disease)
                else:
                    # This would be an orphaned disease if current_chapter is None.
                    # Consider how to handle this based on expected data patterns.
                    # print(f"Warning: Orphaned disease data (no current chapter): {line}")
                    pass


            code = disease_match.group(1)
            name = disease_match.group(2).strip()
            current_disease = {
                "code": code,
                "name": name,
                "description": "",
                "inclusions": []
            }
            continue

        if current_chapter and not current_chapter["chapter_title"] and current_disease is None and not chapter_match and not disease_match:
            current_chapter["chapter_title"] = line
            continue

        inclusion_match = inclusions_re.match(line)
        if inclusion_match:
            if current_disease:
                terms_on_line = inclusion_match.group(1).strip()
                if terms_on_line:
                    current_disease["inclusions"].extend([term.strip() for term in terms_on_line.split(';') if term.strip()])
            continue

        inclusion_item_match = inclusion_item_re.match(line)
        if inclusion_item_match and current_disease:
            term = inclusion_item_match.group(1).strip()
            if term.endswith(';'):
                term = term[:-1].strip()
            current_disease["inclusions"].append(term)
            continue

        if current_disease:
            if current_disease["description"]:
                current_disease["description"] += " " + line
            else:
                current_disease["description"] = line
        elif current_chapter and not current_chapter["chapter_title"] and not current_disease:
            current_chapter["chapter_title"] = line

    if current_disease and current_chapter:
        current_chapter["diseases"].append(current_disease)
    if current_chapter:
        chapters_data.append(current_chapter)

    chapters_data = [ch for ch in chapters_data if ch.get("diseases") or (ch.get("chapter_title") and not ch.get("chapter_title").startswith("Chapter "))]
    # Refined filter: keep chapter if it has diseases OR if its title is not just the "Chapter X" part (meaning a title was found)
    # This also implies that if "Chapter X" is a line and the next line is another "Chapter Y" or EOF, it might be filtered if title is empty.
    # The logic is: a chapter is valid if it has diseases, or if its title field is populated beyond the initial "Chapter X..." part.
    # If chapter_title_candidate was empty and the next line was not a title, it could be an issue.
    # The current logic: `current_chapter["chapter_title"] = line` handles the next line as title.

    final_chapters = []
    for ch in chapters_data:
        # Ensure chapter_title is not just the roman numeral part if it was not updated by a subsequent line.
        # This is a bit of a safeguard. The main logic should capture titles correctly.
        if ch.get("chapter_title") == "" and ch.get("diseases"): # Title might have been missed
            # This situation is less likely with current parsing but good to be aware of.
            # Default title or error logging could go here.
            # print(f"Warning: Chapter {ch['chapter_id']} has diseases but an empty title string.")
            pass # Or assign a default title: ch["chapter_title"] = f"Chapter {ch['chapter_id']} - Title Missing"

        # Filter out chapters that might be empty due to parsing artifacts, e.g. no title and no diseases
        if ch.get("diseases") or (ch.get("chapter_title") and ch.get("chapter_title") != ch.get("chapter_id")): # chapter_id is "01", title should be more
             final_chapters.append(ch)

    print(f"DEBUG: Parser produced {len(final_chapters)} chapter structures.")
    if not final_chapters and raw_data:
        print("DEBUG: Warning: Raw data was present in icd_data.json, but no valid chapter structures were parsed. Check data format compatibility with parser regexes.")
    return final_chapters

def save_structured_data(data, output_filepath="structured_icd_data.json"):
    """
    Saves the structured data to a JSON file.
    """
    if data is None:
        print("No data provided to save.")
        return
    try:
        with open(output_filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Structured data successfully saved to {output_filepath}")
    except IOError:
        print(f"Error: Could not write to file {output_filepath}")
    except Exception as e:
        print(f"An unexpected error occurred while saving data: {e}")

def extract_diagnostico_data(parsed_data):
    """
    Extracts a flat list of disease codes and names for the Diagnostico table.
    """
    if parsed_data is None:
        print("No parsed data provided to extract diagnostico entries.")
        return []

    diagnostico_entries = []
    for chapter in parsed_data:
        if "diseases" in chapter and chapter["diseases"]:
            for disease in chapter["diseases"]:
                diagnostico_entries.append({
                    "codigo": disease.get("code", "N/A"),
                    "descripcion": disease.get("name", "N/A")
                })
    print(f"DEBUG: Extractor found {len(diagnostico_entries)} disease entries from {len(parsed_data) if parsed_data else 0} parsed chapter structure(s).")
    if not diagnostico_entries and parsed_data:
        print("DEBUG: Warning: Chapters were parsed, but no disease entries could be extracted from them. Check chapter content and disease definitions.")
    return diagnostico_entries


if __name__ == "__main__":
    corrected_dummy_icd_data = [
        "Chapter I",
        "Certain infectious or parasitic diseases",
        None,
        "1A00 Cholera",
        "Cholera is a potentially epidemic and life-threatening bacterial disease that is caused by Vibrio cholerae.",
        "It is typically transmitted through contaminated water or food.",
        "Symptoms can include severe watery diarrhea, vomiting, and dehydration.",
        "Inclusions: cholera syndrome; classical cholera; El Tor cholera",
        None,
        "1A01 Intestinal infection due to other Vibrio",
        "This category is for infections caused by Vibrio species other than V. cholerae.",
        None,
        "1A01.0 Intestinal infection due to Vibrio parahaemolyticus",
        "Usually associated with consumption of raw or undercooked seafood.",
        "Inclusions: foodborne intoxication by Vibrio parahaemolyticus; seafood poisoning by V. parahaemolyticus",
        None,
        "1A0Z Intestinal infections due to other Vibrio, unspecified",
        "A long description that spans",
        "multiple lines and needs to be",
        "correctly associated with 1A0Z.",
        "Inclusions: vibrio infection NOS; atypical vibrio infection",
        None,
        "Chapter II",
        "Neoplasms",
        None,
        "2A00 Malignant neoplasm of lip",
        "This is a description for malignant neoplasm of lip, also known as lip cancer.",
        "It often appears as a sore on the lip that does not heal.",
        "Inclusions: cancer of lip; labial carcinoma",
        "Exclusions: skin cancer of lip (Block X)",
        None,
        "2A01 Malignant neoplasm of base of tongue",
        "Description for base of tongue cancer. This can be aggressive.",
        None,
        "2B5F Malignant neoplasms, stated or presumed to be primary, of specified sites, unspecified",
        "This is a catch-all description for primary malignant neoplasms of specified sites but not further detailed.",
        "Inclusions: primary cancer of unspecified site; generalized cancer, primary site specified",
        None,
        "Chapter III",
        "Diseases of the blood or blood-forming organs", # This chapter has no diseases in this dummy set
        None,
        "Chapter IV",
        "Endocrine, nutritional or metabolic diseases",
        "EA00 Diabetes mellitus",
        "Description for Diabetes.",
        "Inclusions: type 1 diabetes; type 2 diabetes; gestational diabetes"
    ]

    dummy_file_path = "icd_data.json"
    with open(dummy_file_path, 'w') as f:
        json.dump(corrected_dummy_icd_data, f, indent=4)
    print(f"Dummy ICD data written to {dummy_file_path}")

    structured_data = parse_icd_json(dummy_file_path)

    if structured_data:
        # Save the structured data
        save_structured_data(structured_data, "structured_icd_data.json")

        # Extract and print Diagnostico data
        diagnostico_entries = extract_diagnostico_data(structured_data)
        if diagnostico_entries:
            print("\nSample of data for Diagnostico table (first 5 entries):")
            for entry in diagnostico_entries[:5]:
                print(entry)
            if len(diagnostico_entries) > 5:
                print(f"... and {len(diagnostico_entries) - 5} more entries.")
        else:
            print("\nNo data extracted for Diagnostico table.")

        # Optional: Keep the validation part for console feedback during testing
        print("\nProcessed ICD Data (from parse_icd_json):")
        print(json.dumps(structured_data, indent=4)) # Still useful to see full structure

        print("\nRunning basic validation on parsed data...")
        # (Validation logic from previous step can be kept here if desired for quick checks)
        if len(structured_data) >= 3:
            print("Validation: Correct number of chapters processed (>=3).")
        else:
            print(f"Validation Error: Expected >=3 chapters with diseases, found {len(structured_data)}")

        chapter_i = next((ch for ch in structured_data if ch["chapter_id"] == "01"), None)
        if chapter_i and chapter_i["chapter_title"] == "Certain infectious or parasitic diseases":
            print("Validation: Chapter I found and title is correct.")
        else:
            print("Validation Error: Chapter I missing or title incorrect.")

        # ... (other validation checks can be added or maintained)

    else:
        print("Failed to parse ICD data.")

    # import os
    # os.remove(dummy_file_path) # Clean up dummy input file
    # print(f"\nDummy file {dummy_file_path} removed.")
    # os.remove("structured_icd_data.json") # Clean up dummy output file
    # print(f"Structured data file structured_icd_data.json removed.")
