import unittest
import os
import requests # Added import for requests.exceptions.RequestException
import time # Added for unique document generation
from unittest.mock import patch, MagicMock

# Temporarily adjust sys.path if your models/app are not directly importable
# This might be needed if 'index' or 'models' are not in the Python path during testing
# import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # Adjust as needed

from index import app, db
from models import Paciente, HistoriaClinica, User # Assuming User is needed for context or future tests
from icd_api_service import get_icd_api_token, search_icd_codes

class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        # Suppress CSRF protection for testing forms if WTForms is used (not explicitly mentioned but good practice)
        app.config['WTF_CSRF_ENABLED'] = False
        # Suppress login_required decorator if Flask-Login is used extensively and not the focus of these tests
        # app.config['LOGIN_DISABLED'] = True # Or mock login_required decorator

        with app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def setUp(self):
        # Runs before each test method
        with app.app_context():
            # Clear all data from tables before each test
            # For more complex scenarios, consider transactions or selective deletion
            # More aggressive/direct cleanup for tables involved in tests:
            HistoriaClinica.query.delete() # Delete children first
            Paciente.query.delete()
            # meta = db.metadata
            # for table in reversed(meta.sorted_tables):
            #     db.session.execute(table.delete())
            db.session.commit()

    def tearDown(self):
        # Runs after each test method
        with app.app_context():
            db.session.remove() # Ensures session is closed

class PatientDeletionTests(BaseTestCase):
    def test_cascade_delete_paciente_historias(self):
        with app.app_context():
            # 1. Create a Paciente
            paciente = Paciente(nombre="Test Paciente", edad=30, documento="12345678")
            db.session.add(paciente)
            db.session.commit()
            paciente_id = paciente.id

            # 2. Create associated HistoriaClinica records
            historia1 = HistoriaClinica(motivo="Consulta General", paciente_id=paciente_id)
            historia2 = HistoriaClinica(motivo="Seguimiento", paciente_id=paciente_id)
            db.session.add_all([historia1, historia2])
            db.session.commit()

            self.assertEqual(HistoriaClinica.query.filter_by(paciente_id=paciente_id).count(), 2)

            # 1. Create a Paciente
            # Using a unique document for this specific test run to avoid UNIQUE constraint issues
            # that seem to stem from test setup/teardown problems.
            unique_documento = f"12345678_{time.time()}"
            paciente = Paciente(nombre="Test Paciente", edad=30, documento=unique_documento)
            db.session.add(paciente)
            db.session.commit() # Commit paciente first to get ID
            paciente_id = paciente.id

            # 2. Create associated HistoriaClinica records
            historia1 = HistoriaClinica(motivo="Consulta General", paciente_id=paciente_id)
            historia2 = HistoriaClinica(motivo="Seguimiento", paciente_id=paciente_id)
            # Add historias to patient's collection AND to session
            paciente.historias.append(historia1)
            paciente.historias.append(historia2)
            db.session.add(paciente) # Add paciente again to associate historias in session
            db.session.commit()

            historia1_id = historia1.id
            historia2_id = historia2.id

            self.assertEqual(HistoriaClinica.query.filter_by(paciente_id=paciente_id).count(), 2)

            # Test delete-orphan by removing from collection
            paciente.historias.remove(historia1)
            db.session.commit()

            self.assertIsNone(HistoriaClinica.query.get(historia1_id))
            self.assertEqual(HistoriaClinica.query.filter_by(paciente_id=paciente_id).count(), 1)

            # Test cascade delete by deleting the parent
            db.session.delete(paciente)
            db.session.commit()

            self.assertIsNone(Paciente.query.get(paciente_id))
            self.assertIsNone(HistoriaClinica.query.get(historia2_id))
            self.assertEqual(HistoriaClinica.query.filter_by(paciente_id=paciente_id).count(), 0)

class ICDApiServiceTests(BaseTestCase):
    def test_get_token_missing_credentials(self):
        with patch.dict(os.environ, {}, clear=True): # Ensure env vars are clear for this test
            token, status = get_icd_api_token()
            self.assertIsNone(token)
            self.assertEqual(status, "MISSING_CREDENTIALS")

            # Test search_icd_codes propagation of this error
            results, search_status = search_icd_codes("test")
            self.assertIsNone(results)
            self.assertEqual(search_status, "MISSING_CREDENTIALS")

    @patch('icd_api_service.requests.post')
    def test_get_token_request_failed(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("Simulated API error")

        # Set dummy credentials to pass the initial check
        with patch.dict(os.environ, {"ICD_API_CLIENT_ID": "dummy", "ICD_API_CLIENT_SECRET": "dummy"}):
            token, status = get_icd_api_token()
            self.assertIsNone(token)
            self.assertEqual(status, "TOKEN_REQUEST_FAILED")

    @patch('icd_api_service.requests.post')
    def test_get_token_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "fake_token", "expires_in": 3600}
        mock_response.raise_for_status = MagicMock() # Ensure it doesn't raise
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"ICD_API_CLIENT_ID": "dummy", "ICD_API_CLIENT_SECRET": "dummy"}):
            token, status = get_icd_api_token()
            self.assertEqual(token, "fake_token")
            self.assertEqual(status, "SUCCESS")

    @patch('icd_api_service.get_icd_api_token', return_value=("fake_token", "SUCCESS")) # Mock successful token
    @patch('icd_api_service.requests.get')
    def test_search_codes_api_error(self, mock_get, mock_get_token):
        mock_get.side_effect = requests.exceptions.RequestException("Simulated API search error")

        results, status = search_icd_codes("diabetes")
        self.assertIsNone(results)
        self.assertEqual(status, "SEARCH_API_ERROR")

    @patch('icd_api_service.get_icd_api_token', return_value=("fake_token", "SUCCESS")) # Mock successful token
    @patch('icd_api_service.requests.get')
    def test_search_codes_success(self, mock_get, mock_get_token):
        mock_response = MagicMock()
        # Simplified expected structure from your search_icd_codes function
        mock_response.json.return_value = {
            "destinationEntities": [
                {"id": "http://id.who.int/icd/entity/123", "title": {"@value": "Diabetes Mellitus"}},
                {"id": "http://id.who.int/icd/entity/456", "title": {"@value": "Type 1 Diabetes"}}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        expected_results = [
            {"id": "http://id.who.int/icd/entity/123", "label": "Diabetes Mellitus", "raw_id": "http://id.who.int/icd/entity/123", "raw_title": {"@value": "Diabetes Mellitus"}},
            {"id": "http://id.who.int/icd/entity/456", "label": "Type 1 Diabetes", "raw_id": "http://id.who.int/icd/entity/456", "raw_title": {"@value": "Type 1 Diabetes"}}
        ]

        results, status = search_icd_codes("diabetes")
        self.assertEqual(results, expected_results)
        self.assertEqual(status, "SUCCESS")

# This allows running tests from the command line
if __name__ == '__main__':
    # Need to import requests for the RequestException in mock
    import requests
    unittest.main()
