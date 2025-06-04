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

# This allows running tests from the command line
if __name__ == '__main__':
    # Need to import requests for the RequestException in mock
    import requests
    unittest.main()
