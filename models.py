from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Paciente(db.Model):
    __tablename__ = 'paciente'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    edad = db.Column(db.Integer, nullable=False)
    documento = db.Column(db.String(50), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    correo = db.Column(db.String(120))

    historias = db.relationship('HistoriaClinica', backref='paciente', lazy=True)
    citas = db.relationship('Cita', backref='paciente_cita', lazy=True, cascade="all, delete-orphan")

class HistoriaClinica(db.Model):
    __tablename__ = 'historia_clinica'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    motivo = db.Column(db.String(255), nullable=False)
    diagnostico = db.Column(db.String(255), nullable=True)
    tratamiento = db.Column(db.String(255), nullable=True)
    observaciones = db.Column(db.Text, nullable=True)

    # Clave foránea que relaciona con el paciente
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)


class Cita(db.Model):
    __tablename__ = 'cita'
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Add default for now
    motivo = db.Column(db.String(255), nullable=False)
    notas = db.Column(db.Text, nullable=True)

    # Consider adding a relationship to Paciente if needed for easy access from Cita to Paciente details
    # paciente = db.relationship('Paciente', backref=db.backref('citas_paciente', lazy=True)) 
    # The backref on Paciente model will handle the other side.