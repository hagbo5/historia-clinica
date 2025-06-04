# Project Documentation

This document provides an overview of the project and key functionalities, including the local ICD data integration.

## Local ICD Data Integration

The application has been configured to use a local source for International Classification of Diseases (ICD) data, replacing the previous reliance on an external WHO API. This allows for offline use and customized data management.

### 1. Source ICD Data File (`icd_data.json`)

*   **Location:** The primary source file for ICD data must be placed in the project's root directory and named `icd_data.json`.
*   **Format:** This file is expected to be a JSON array (list) where each element is either:
    *   A string, representing a line from the original ICD textual document. This can include chapter titles, disease codes with names, descriptions, inclusion/exclusion notes, or other metadata.
    *   A `null` value, which might be used as a separator in the original document (they are ignored by the parser).
    *   The parser (`process_local_icd.py`) is designed to handle variations, such as chapter titles, disease codes, and descriptions appearing on separate lines or being part of simple string entries.
*   **Example Snippet of `icd_data.json` content:**
    ```json
    [
      "Chapter I",
      "Certain infectious or parasitic diseases",
      null,
      "1A00 Cholera",
      "Cholera is a potentially epidemic and life-threatening bacterial disease that is caused by Vibrio cholerae.",
      "It is typically transmitted through contaminated water or food.",
      "Inclusions: cholera syndrome; classical cholera; El Tor cholera",
      null,
      "1A01 Intestinal infection due to other Vibrio",
      "This category is for infections caused by Vibrio species other than V. cholerae.",
      null,
      "Chapter II",
      "Neoplasms"
    ]
    ```
    *(Note: This example shows a simplified structure. The actual `icd_data.json` used by `process_local_icd.py` during its own tests and by `scriptss/populate_diagnostico_db.py` during its tests is a list of strings and nulls, which the parser correctly processes.)*
*   **Updating:** To update the ICD data, replace the `icd_data.json` file with the new version containing the complete data in the expected format. After updating, you **must** run the processing and database population scripts (see below).

### 2. Key Scripts and Their Roles

*   **`process_local_icd.py`:**
    *   This script is responsible for parsing the raw `icd_data.json` file (which is expected to be a list of strings/nulls).
    *   It generates a structured JSON file named `structured_icd_data.json` (in the root directory). This file contains the fully parsed and hierarchical ICD data (chapters, diseases with codes, names, detailed descriptions, inclusions, etc.) and is used by the application for detailed lookups.
    *   It also provides functions to extract a simplified list of codes and their primary names, which is used for populating the database.
    *   To regenerate `structured_icd_data.json` after updating `icd_data.json`, you can run this script directly: `python process_local_icd.py`. The script's `if __name__ == "__main__":` block creates a dummy `icd_data.json` and then processes it into `structured_icd_data.json`. For production use, you'd replace the root `icd_data.json` with your actual data first.

*   **`scriptss/populate_diagnostico_db.py`:**
    *   This script takes the data extracted by `process_local_icd.py` (which reads from the root `icd_data.json`) and populates/updates the `Diagnostico` table in the application's database.
    *   **Crucial:** This script **must be run** whenever the main `icd_data.json` is updated to ensure the database reflects the latest ICD codes and descriptions.
    *   To run it: `python scriptss/populate_diagnostico_db.py`. (Ensure your Flask app environment is correctly configured, including necessary Python packages like Flask, Flask-SQLAlchemy, etc., for the script to access the database).

*   **`local_icd_service.py`:**
    *   This service module loads the `structured_icd_data.json` file into memory (with caching) and provides functions for the application to access detailed ICD information (e.g., get chapter details, get full disease descriptions, search local data).

*   **`icd_api_service.py`:**
    *   This service, previously used for WHO API calls, has been refactored. It now acts as an interface to the `local_icd_service.py`, ensuring that the rest of the application can request ICD data in a consistent way, now sourced locally.

### 3. Data Flow Overview

1.  The raw ICD data is provided in `icd_data.json` (as a list of strings/nulls).
2.  `python process_local_icd.py` is run:
    *   It parses `icd_data.json` (if using its main block, it first creates a dummy version of this file for demonstration).
    *   It generates `structured_icd_data.json` (for rich, detailed lookups by `local_icd_service.py`).
3.  `python scriptss/populate_diagnostico_db.py` is run:
    *   It uses helper functions from `process_local_icd.py` to parse the root `icd_data.json` and extract code/description pairs.
    *   It updates the `Diagnostico` table in the database. This table is primarily used for linking diagnoses to patient records.
4.  The application, via `icd_api_service.py` (which uses `local_icd_service.py`):
    *   Performs searches for ICD codes and retrieves chapter information and detailed disease data primarily from `structured_icd_data.json`.
    *   The `Diagnostico` table serves as a quick lookup for codes and primary names and for establishing relationships in the database.

### 4. Setup and Usage Summary

1.  Place your complete ICD data file (formatted as a JSON list of strings and nulls, representing the textual lines of your ICD document) as `icd_data.json` in the project root.
2.  Run `python process_local_icd.py`. This will parse your `icd_data.json` and generate/update `structured_icd_data.json`.
3.  Run `python scriptss/populate_diagnostico_db.py`. This will use your `icd_data.json` to update the `Diagnostico` table in the application's database.
4.  Run the Flask application (e.g., `python index.py`).

The ICD search, chapter browsing, and diagnostico selection functionalities should now use this local data.
```
