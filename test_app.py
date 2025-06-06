import unittest
import os
import requests # Added import for requests.exceptions.RequestException
import time # Added for unique document generation
from unittest.mock import patch, MagicMock

# Temporarily adjust sys.path if your models/app are not directly importable
# This might be needed if 'index' or 'models' are not in the Python path during testing
# import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # Adjust as needed
from flask import url_for

from index import app, db
from models import Paciente, HistoriaClinica, User, Diagnostico, Tratamiento # Added Diagnostico, Tratamiento
from icd_api_service import search_icd_codes

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
            HistoriaClinica.query.delete()
            Paciente.query.delete()
            Diagnostico.query.delete() # Added Diagnostico cleanup
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

class ClinicalHistoryFormTests(BaseTestCase):
    def _login(self, username, password):
        # Check if user exists, if not create one
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

        # Use self.client provided by Flask's test app
        return self.client.post(url_for('login'), data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def setUp(self):
        super().setUp() # Call BaseTestCase's setUp
        # Create a test client for making requests
        self.client = app.test_client()
        # Create a test user for login, if not already handled by _login or specific tests
        # For simplicity, _login will handle user creation if needed.

    def test_nueva_historia_form_loads_diagnosticos_dropdown(self):
        with app.app_context():
            self._login('testuserform', 'password123')

            paciente_doc = f"FORMTEST_{time.time()}"
            paciente = Paciente(nombre='Test Paciente Form', edad=30, documento=paciente_doc)
            db.session.add(paciente)
            db.session.commit()

            diag1_code = f"TEST01_{time.time()}"
            diag1 = Diagnostico(codigo=diag1_code, descripcion='Test Diagnostico Uno')
            db.session.add(diag1)
            db.session.commit()

            response = self.client.get(url_for('nueva_historia', paciente_id=paciente.id))

            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="diagnosticos_seleccionados"', response.data)
            self.assertIn(b'name="diagnosticos_seleccionados"', response.data)
            self.assertIn(b'Test Diagnostico Uno', response.data)
            self.assertIn(diag1_code.encode('utf-8'), response.data)

            # Clean up (optional here as setUp clears tables, but good for explicitness if needed)
            # db.session.delete(diag1)
            # db.session.delete(paciente)
            # db.session.commit()

    def test_editar_historia_form_loads_diagnosticos_dropdown(self):
        with app.app_context():
            self._login('testuserformedit', 'password123')

            paciente_doc_edit = f"FORMEDIT_{time.time()}"
            paciente = Paciente(nombre='Test Paciente Edit Form', edad=31, documento=paciente_doc_edit)
            db.session.add(paciente)
            db.session.commit() # Commit paciente to get its ID

            historia = HistoriaClinica(motivo='Test Motivo Edit', paciente_id=paciente.id)
            db.session.add(historia)
            db.session.commit() # Commit historia to get its ID

            diag2_code = f"TEST02_{time.time()}"
            diag2 = Diagnostico(codigo=diag2_code, descripcion='Test Diagnostico Dos')
            db.session.add(diag2)
            db.session.commit()

            response = self.client.get(url_for('editar_historia', paciente_id=paciente.id, historia_id=historia.id))

            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="diagnosticos_seleccionados"', response.data)
            self.assertIn(b'name="diagnosticos_seleccionados"', response.data)
            self.assertIn(b'Test Diagnostico Dos', response.data)
            self.assertIn(diag2_code.encode('utf-8'), response.data)

            # Clean up (optional here)
            # db.session.delete(diag2)
            # db.session.delete(historia)
            # db.session.delete(paciente)
            # db.session.commit()

# This allows running tests from the command line
if __name__ == '__main__':
    # Need to import requests for the RequestException in mock
    import requests
    unittest.main()
