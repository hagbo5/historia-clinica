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

    historias = db.relationship('HistoriaClinica', backref='paciente', lazy=True, cascade="all, delete-orphan")
    citas = db.relationship('Cita', backref='paciente_cita', lazy=True, cascade="all, delete-orphan")
    facturas = db.relationship('Factura', backref='paciente', lazy='dynamic', cascade="all, delete-orphan")

# Association table for HistoriaClinica and Diagnostico
historia_diagnostico_association = db.Table('historia_diagnostico_association',
    db.Column('historia_clinica_id', db.Integer, db.ForeignKey('historia_clinica.id'), primary_key=True),
    db.Column('diagnostico_id', db.Integer, db.ForeignKey('diagnostico.id'), primary_key=True)
)

# Association table for HistoriaClinica and Tratamiento
historia_tratamiento_association = db.Table('historia_tratamiento_association',
    db.Column('historia_clinica_id', db.Integer, db.ForeignKey('historia_clinica.id'), primary_key=True),
    db.Column('tratamiento_id', db.Integer, db.ForeignKey('tratamiento.id'), primary_key=True)
)

class HistoriaClinica(db.Model):
    __tablename__ = 'historia_clinica'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    motivo = db.Column(db.String(255), nullable=False)
    observaciones = db.Column(db.Text, nullable=True)

    # Clave foránea que relaciona con el paciente
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)

    diagnosticos = db.relationship(
        'Diagnostico', 
        secondary=historia_diagnostico_association,
        backref=db.backref('historias_clinicas_associated', lazy='dynamic'),
        lazy='dynamic'
    )

    tratamientos = db.relationship(
        'Tratamiento', 
        secondary=historia_tratamiento_association,
        backref=db.backref('historias_clinicas_con_tratamiento', lazy='dynamic'),
        lazy='dynamic'
    )


class Cita(db.Model):
    __tablename__ = 'cita'
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) 
    motivo = db.Column(db.String(255), nullable=False)
    notas = db.Column(db.Text, nullable=True)

    # The backref on Paciente model will handle the other side.


class Diagnostico(db.Model):
    __tablename__ = 'diagnostico'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Diagnostico {self.codigo} - {self.descripcion[:30]}>'


class Tratamiento(db.Model):
    __tablename__ = 'tratamiento'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    costo = db.Column(db.Numeric(10, 2), nullable=True)  # For storing cost

    def __repr__(self):
        return f'<Tratamiento {self.codigo} - {self.descripcion[:30]}>'


class Factura(db.Model):
    __tablename__ = 'factura'
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)
    numero_factura = db.Column(db.String(50), unique=True, nullable=False)
    fecha_emision = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.Date, nullable=True)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    estado = db.Column(db.String(20), nullable=False, default='Pendiente')  # E.g., Pendiente, Pagada, Anulada

    # Relationship to Items
    items = db.relationship('ItemFactura', backref='factura', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Factura {self.numero_factura} - {self.estado}>'


class ItemFactura(db.Model):
    __tablename__ = 'item_factura'
    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(db.Integer, db.ForeignKey('factura.id'), nullable=False)
    descripcion = db.Column(db.String(255), nullable=False)
    tratamiento_id = db.Column(db.Integer, db.ForeignKey('tratamiento.id'), nullable=True) # Optional
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False) # Should be pre-calculated

    # Optional: Relationship to Tratamiento model for easy access
    tratamiento = db.relationship('Tratamiento')

    def __repr__(self):
        return f'<ItemFactura {self.descripcion[:50]} - Qty: {self.cantidad}>'

    def calculate_subtotal(self):
        self.subtotal = self.cantidad * self.precio_unitario
        return self.subtotal