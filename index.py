from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from models import db, User, Paciente, HistoriaClinica, Cita # Asegúrate de importar User desde models.py
from models import Paciente
from sqlalchemy.exc import IntegrityError
from datetime import datetime


app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Define la función user_loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def inicio():
    return render_template('inicio.html')


@app.route('/home')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))  # Redirige a la página de inicio
        else:
            flash('Credenciales incorrectas')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Las contraseñas no coinciden.')
            return redirect(url_for('register'))

        # Verificar si el usuario ya existe
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya está en uso. Elige otro.')
            return redirect(url_for('register'))

        # Crear un nuevo usuario
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Cuenta creada con éxito. Ahora puedes iniciar sesión.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()  # Cierra la sesión de Flask-Login
    flash("Has cerrado sesión.")
    return redirect(url_for('inicio'))


@app.route('/pacientes')
@login_required
def pacientes():
    pacientes = Paciente.query.all()  # Suponiendo que tienes un modelo Paciente
    q = request.args.get('buscar')
    if q:
        pacientes = Paciente.query.filter(
            (Paciente.nombre.ilike(f"%{q}%")) | (Paciente.documento.ilike(f"%{q}%"))
        ).all()
    else:
        pacientes = Paciente.query.all()

    return render_template('pacientes.html', pacientes=pacientes)

@app.route('/pacientes/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_paciente():
    if request.method == 'POST':
        nombre = request.form['nombre']
        edad = request.form['edad']
        documento = request.form['documento']
        telefono = request.form.get('telefono')
        direccion = request.form.get('direccion')
        correo = request.form.get('correo')

        if Paciente.query.filter_by(documento=documento).first():
            flash('Ya existe un paciente con ese número de documento.')
            return redirect(url_for('nuevo_paciente'))

        
        nuevo = Paciente(nombre=nombre, edad=edad, documento=documento, telefono=telefono, direccion=direccion, correo=correo)
        db.session.add(nuevo)
        try:
            db.session.commit()
            flash('Paciente creado correctamente.')
        except IntegrityError:
            db.session.rollback()
            flash('Ya existe un paciente con ese número de documento.')
            return redirect(url_for('nuevo_paciente'))
        return redirect(url_for('pacientes'))
    return render_template('nuevo_paciente.html')


@app.route('/pacientes/<int:id>')
@login_required
def ver_paciente(id):
    paciente = Paciente.query.get_or_404(id)
    return render_template('ver_paciente.html', paciente=paciente)

@app.route('/pacientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_paciente(id):
    paciente = Paciente.query.get_or_404(id)
    if request.method == 'POST':
        paciente.nombre = request.form['nombre']
        paciente.edad = request.form['edad']
        paciente.documento = request.form['documento']
        paciente.telefono = request.form.get('telefono')
        paciente.direccion = request.form.get('direccion')
        paciente.correo = request.form.get('correo')
        try:
            db.session.commit()
            flash('Paciente actualizado correctamente.')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al actualizar el paciente.')
        return redirect(url_for('pacientes'))
    return render_template('editar_paciente.html', paciente=paciente)

@app.route('/pacientes/<int:id>/eliminar', methods=['GET', 'POST'])
@login_required
def eliminar_paciente(id):
    paciente = Paciente.query.get_or_404(id)
    try:
        db.session.delete(paciente)
        db.session.commit()
        flash('Paciente eliminado correctamente.')
    except Exception as e:
        db.session.rollback()
        flash('Error al eliminar el paciente.')
    return redirect(url_for('pacientes'))

@app.route('/pacientes/<int:paciente_id>/historias')
@login_required
def listar_historias(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    # paciente.historias -> lista de historias asociadas
    return render_template('listar_historias.html', paciente=paciente)

@app.route('/pacientes/<int:paciente_id>/historias/nuevo', methods=['GET', 'POST'])
@login_required
def nueva_historia(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    if request.method == 'POST':
        motivo = request.form['motivo']
        diagnostico = request.form.get('diagnostico')
        tratamiento = request.form.get('tratamiento')
        observaciones = request.form.get('observaciones')

        nueva = HistoriaClinica(
            motivo=motivo,
            diagnostico=diagnostico,
            tratamiento=tratamiento,
            observaciones=observaciones,
            paciente_id=paciente.id
        )
        db.session.add(nueva)
        db.session.commit()
        flash('Historia creada correctamente.')
        return redirect(url_for('listar_historias', paciente_id=paciente.id))
    return render_template('nueva_historia.html', paciente=paciente)

@app.route('/historias/<int:id>')
@login_required
def ver_historia(id):
    historia = HistoriaClinica.query.get_or_404(id)
    return render_template('ver_historia.html', historia=historia)


@app.route('/pacientes/<int:paciente_id>/historias/<int:historia_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_historia(paciente_id, historia_id):
    historia = HistoriaClinica.query.get_or_404(historia_id)
    paciente = Paciente.query.get_or_404(paciente_id)
    if request.method == 'POST':
        historia.motivo = request.form['motivo']
        historia.diagnostico = request.form.get('diagnostico')
        historia.tratamiento = request.form.get('tratamiento')
        historia.observaciones = request.form.get('observaciones')
        try:
            db.session.commit()
            flash('Historia clínica actualizada correctamente.')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al actualizar la historia clínica.')
        return redirect(url_for('listar_historias', paciente_id=paciente_id))
    return render_template('editar_historia.html', historia=historia, paciente=paciente)


@app.route('/pacientes/<int:paciente_id>/historias/<int:historia_id>/eliminar', methods=['POST'])
@login_required
def eliminar_historia(paciente_id, historia_id):
    historia = HistoriaClinica.query.get_or_404(historia_id)
    try:
        db.session.delete(historia)
        db.session.commit()
        flash('Historia clínica eliminada correctamente.')
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al eliminar la historia clínica.')
    return redirect(url_for('listar_historias', paciente_id=paciente_id))


@app.route('/citas')
@login_required
def citas():
    todas_las_citas = Cita.query.order_by(Cita.fecha_hora.desc()).all()
    return render_template('citas.html', citas=todas_las_citas)


@app.route('/pacientes/<int:paciente_id>/citas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_cita_paciente(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    if request.method == 'POST':
        fecha_hora_str = request.form['fecha_hora']
        motivo = request.form['motivo']
        notas = request.form.get('notas')
        
        try:
            fecha_hora = datetime.strptime(fecha_hora_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Formato de fecha y hora inválido. Use YYYY-MM-DDTHH:MM.')
            return render_template('nueva_cita.html', paciente=paciente, cita=None)

        nueva = Cita(paciente_id=paciente.id, fecha_hora=fecha_hora, motivo=motivo, notas=notas)
        db.session.add(nueva)
        db.session.commit()
        flash('Cita creada correctamente.')
        return redirect(url_for('listar_citas_paciente', paciente_id=paciente.id))
    return render_template('nueva_cita.html', paciente=paciente, cita=None)


@app.route('/pacientes/<int:paciente_id>/citas')
@login_required
def listar_citas_paciente(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    return render_template('paciente_citas.html', paciente=paciente, citas=paciente.citas)


@app.route('/citas/<int:cita_id>')
@login_required
def ver_cita(cita_id):
    cita = Cita.query.get_or_404(cita_id)
    return render_template('ver_cita.html', cita=cita)


@app.route('/citas/<int:cita_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cita(cita_id):
    cita = Cita.query.get_or_404(cita_id)
    paciente = Paciente.query.get_or_404(cita.paciente_id)
    if request.method == 'POST':
        fecha_hora_str = request.form['fecha_hora']
        try:
            cita.fecha_hora = datetime.strptime(fecha_hora_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Formato de fecha y hora inválido. Use YYYY-MM-DDTHH:MM.')
            return render_template('nueva_cita.html', cita=cita, paciente=paciente)

        cita.motivo = request.form['motivo']
        cita.notas = request.form.get('notas')
        db.session.commit()
        flash('Cita actualizada correctamente.')
        return redirect(url_for('ver_cita', cita_id=cita.id))
    return render_template('nueva_cita.html', cita=cita, paciente=paciente)


@app.route('/citas/<int:cita_id>/eliminar', methods=['POST'])
@login_required
def eliminar_cita(cita_id):
    cita = Cita.query.get_or_404(cita_id)
    paciente_id = cita.paciente_id
    db.session.delete(cita)
    db.session.commit()
    flash('Cita eliminada correctamente.')
    paciente = Paciente.query.get(paciente_id)
    if paciente:
        return redirect(url_for('listar_citas_paciente', paciente_id=paciente_id))
    else:
        return redirect(url_for('citas'))


# Aquí puedes añadir más rutas y lógica para tu aplicación

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
