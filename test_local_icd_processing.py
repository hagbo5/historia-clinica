import unittest
from unittest.mock import patch, mock_open
import json
import os
import tempfile

# Modules to be tested
import process_local_icd
import local_icd_service

class TestProcessLocalICD(unittest.TestCase):

    def setUp(self):
        self.sample_raw_icd_data_list = [
            "Chapter I",
            "Certain infectious or parasitic diseases",
            None,
            "1A00 Cholera",
            "Cholera is an acute diarrhoeal infection caused by ingestion of food or water contaminated with the bacterium Vibrio cholerae.",
            "Inclusions: classical cholera; El Tor cholera",
            None,
            "1A01 Intestinal infection due to other Vibrio",
            "Excludes: cholera (1A00)", # Description part
            None, # No inclusions for this one
            "Chapter II",
            "Neoplasms",
            "2A00 Malignant neoplasm of lip",
            "Description for lip cancer."
        ]
        self.expected_structured_data_from_sample = [
            {
                "chapter_id": "01",
                "chapter_title": "Certain infectious or parasitic diseases",
                "diseases": [
                    {
                        "code": "1A00",
                        "name": "Cholera",
                        "description": "Cholera is an acute diarrhoeal infection caused by ingestion of food or water contaminated with the bacterium Vibrio cholerae.",
                        "inclusions": ["classical cholera", "El Tor cholera"],
                    },
                    {
                        "code": "1A01",
                        "name": "Intestinal infection due to other Vibrio",
                        "description": "Excludes: cholera (1A00)",
                        "inclusions": [],
                    }
                ]
            },
            {
                "chapter_id": "02",
                "chapter_title": "Neoplasms",
                "diseases": [
                    {
                        "code": "2A00",
                        "name": "Malignant neoplasm of lip",
                        "description": "Description for lip cancer.",
                        "inclusions": [],
                    }
                ]
            }
        ]

    @patch("json.load")  # Decorator for json.load
    def test_parse_icd_json_simple(self, mock_for_json_load):
        # mock_for_json_load is the mock for json.load

        # Configure the mock for json.load to return our sample list of strings
        mock_for_json_load.return_value = self.sample_raw_icd_data_list

        # Patch 'open' within 'process_local_icd' module for the scope of this 'with' block
        # mock_open() creates a mock that simulates the open function and its file handle.
        with patch('process_local_icd.open', mock_open()) as mock_open_function_itself:
            # mock_open_function_itself is the mock replacing 'open' in process_local_icd.py
            # Its return_value is the file handle mock, which mock_open() configures to be a context manager.
            result = process_local_icd.parse_icd_json("dummy_path.json")

        # Assertions

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2) # Two chapters expected

        # Chapter I checks
        chapter1 = result[0]
        self.assertEqual(chapter1["chapter_id"], "01")
        self.assertEqual(chapter1["chapter_title"], "Certain infectious or parasitic diseases")
        self.assertEqual(len(chapter1["diseases"]), 2)

        disease1_ch1 = chapter1["diseases"][0]
        self.assertEqual(disease1_ch1["code"], "1A00")
        self.assertEqual(disease1_ch1["name"], "Cholera")
        self.assertIn("Vibrio cholerae", disease1_ch1["description"])
        self.assertListEqual(disease1_ch1["inclusions"], ["classical cholera", "El Tor cholera"])

        disease2_ch1 = chapter1["diseases"][1]
        self.assertEqual(disease2_ch1["code"], "1A01")
        self.assertEqual(disease2_ch1["name"], "Intestinal infection due to other Vibrio")
        self.assertEqual(disease2_ch1["description"], "Excludes: cholera (1A00)")
        self.assertListEqual(disease2_ch1["inclusions"], [])

        # Chapter II checks
        chapter2 = result[1]
        self.assertEqual(chapter2["chapter_id"], "02")
        self.assertEqual(chapter2["chapter_title"], "Neoplasms")
        self.assertEqual(len(chapter2["diseases"]), 1)
        disease1_ch2 = chapter2["diseases"][0]
        self.assertEqual(disease1_ch2["code"], "2A00")
        self.assertEqual(disease1_ch2["name"], "Malignant neoplasm of lip")

    def test_extract_diagnostico_data(self):
        # Use the expected output from the previous test as input here
        sample_parsed_data = self.expected_structured_data_from_sample

        result = process_local_icd.extract_diagnostico_data(sample_parsed_data)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3) # 3 diseases in total

        self.assertDictEqual(result[0], {"codigo": "1A00", "descripcion": "Cholera"})
        self.assertDictEqual(result[1], {"codigo": "1A01", "descripcion": "Intestinal infection due to other Vibrio"})
        self.assertDictEqual(result[2], {"codigo": "2A00", "descripcion": "Malignant neoplasm of lip"})

    # TODO: test_parse_icd_json_edge_cases if time permits


class TestLocalICDService(unittest.TestCase):

    def setUp(self):
        # Reset cache before each test for isolation
        local_icd_service._icd_data_cache = None
        local_icd_service._cache_load_time = None

        self.test_data = [
            {
                "chapter_id": "01",
                "chapter_title": "Chapter One",
                "diseases": [
                    {"code": "A01", "name": "Disease A1", "description": "Description A1. Related to Alpha.", "inclusions": ["InclA1"]},
                    {"code": "A02", "name": "Disease A2", "description": "Description A2", "inclusions": []}
                ]
            },
            {
                "chapter_id": "02",
                "chapter_title": "Chapter Two",
                "diseases": [
                    {"code": "B01", "name": "Disease B1", "description": "Description B1. Alpha and Beta.", "inclusions": ["InclB1"]}
                ]
            }
        ]

        # Create a temporary file for structured_icd_data.json
        self.temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
        json.dump(self.test_data, self.temp_file)
        self.temp_file.close()
        self.temp_file_path = self.temp_file.name

    def tearDown(self):
        os.unlink(self.temp_file_path) # Delete the temporary file

    def test_load_icd_data(self):
        # First call: should load from file
        data = local_icd_service.load_icd_data(file_path=self.temp_file_path)
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["chapter_id"], "01")

        # Check if cache is populated
        self.assertIsNotNone(local_icd_service._icd_data_cache)
        self.assertIsNotNone(local_icd_service._cache_load_time)

        # Second call: should load from cache
        # To verify, mock json.load and ensure it's not called again for this file
        with patch("json.load") as mock_json_load_cache_test:
            mock_json_load_cache_test.side_effect = AssertionError("json.load called when cache should be used")
            data_from_cache = local_icd_service.load_icd_data(file_path=self.temp_file_path)
            self.assertEqual(data_from_cache, data) # Should be same data
            mock_json_load_cache_test.assert_not_called() # Crucial check

    def test_get_chapters(self):
        # Ensure data is loaded via the service's load function
        local_icd_service.load_icd_data(file_path=self.temp_file_path)

        chapters = local_icd_service.get_chapters()
        self.assertEqual(len(chapters), 2)
        self.assertDictEqual(chapters[0], {"chapter_id": "01", "chapter_title": "Chapter One"})
        self.assertDictEqual(chapters[1], {"chapter_id": "02", "chapter_title": "Chapter Two"})

    def test_get_chapter_details(self):
        local_icd_service.load_icd_data(file_path=self.temp_file_path)

        # Existing chapter
        details_01 = local_icd_service.get_chapter_details("01")
        self.assertIsNotNone(details_01)
        self.assertEqual(details_01["chapter_title"], "Chapter One")
        self.assertEqual(len(details_01["diseases"]), 2)

        # Non-existing chapter
        details_99 = local_icd_service.get_chapter_details("99")
        self.assertIsNone(details_99)

    def test_get_disease_details(self):
        local_icd_service.load_icd_data(file_path=self.temp_file_path)

        # Existing disease
        disease_a01 = local_icd_service.get_disease_details("A01")
        self.assertIsNotNone(disease_a01)
        self.assertEqual(disease_a01["name"], "Disease A1")

        # Non-existing disease
        disease_x99 = local_icd_service.get_disease_details("X99")
        self.assertIsNone(disease_x99)

    def test_search_diseases(self):
        local_icd_service.load_icd_data(file_path=self.temp_file_path)

        # Search by name (case-insensitive)
        results_a1 = local_icd_service.search_diseases("disease a1")
        self.assertEqual(len(results_a1), 1)
        self.assertEqual(results_a1[0]["code"], "A01")

        # Search by description content
        results_alpha = local_icd_service.search_diseases("Alpha")
        self.assertEqual(len(results_alpha), 2) # A01 (description) and B01 (description)
        codes_alpha = sorted([d["code"] for d in results_alpha])
        self.assertListEqual(codes_alpha, ["A01", "B01"])


        # Search term not found
        results_zeta = local_icd_service.search_diseases("Zeta")
        self.assertEqual(len(results_zeta), 0)

        # Search by part of name
        results_disease = local_icd_service.search_diseases("Disease")
        self.assertEqual(len(results_disease), 3)


if __name__ == '__main__':
    unittest.main()
