from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user
from models import db, User, Paciente, HistoriaClinica, Cita, Diagnostico, Tratamiento, Factura, ItemFactura # Asegúrate de importar User desde models.py
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from icd_api_service import search_icd_codes, get_icd_chapters


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

# --- Helper Functions for Invoicing ---
def get_next_invoice_number():
    current_year = datetime.utcnow().year
    prefix = f"INV-{current_year}-"
    
    # Find the last invoice for the current year
    last_invoice_for_year = Factura.query.filter(Factura.numero_factura.like(f"{prefix}%")) \
                                       .order_by(Factura.numero_factura.desc()).first()
    
    next_number = 1
    if last_invoice_for_year:
        try:
            # Extract the numeric part and increment
            last_numeric_part = int(last_invoice_for_year.numero_factura.split('-')[-1])
            next_number = last_numeric_part + 1
        except (ValueError, IndexError):
            # Fallback: if parsing fails, count existing invoices for the year and add 1
            # This is a simplified fallback. A more robust solution might involve a dedicated sequence.
            all_year_invoices_count = Factura.query.filter(Factura.numero_factura.like(f"{prefix}%")).count()
            next_number = all_year_invoices_count + 1

    return f"{prefix}{next_number:04d}" # Ensures 4-digit padding

def calculate_and_update_invoice_total(factura_id):
    factura = Factura.query.get(factura_id) 
    if not factura:
        # Log or handle error: Factura not found
        print(f"Error: Factura with ID {factura_id} not found for total calculation.")
        return

    new_total = sum(float(item.subtotal) for item in factura.items)
    factura.total = round(new_total, 2)
    
    try:
        db.session.add(factura) # Ensure factura is part of the session for update
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Consider logging this error more formally
        print(f"Error calculating/updating total for factura {factura.id}: {e}")
        # Depending on context, might re-raise or flash a message if called from a route

# --- End Helper Functions ---

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
    return render_template('listar_historias.html', paciente=paciente)

@app.route('/pacientes/<int:paciente_id>/historias/nuevo', methods=['GET', 'POST'])
@login_required
def nueva_historia(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    diagnosticos_catalogo = Diagnostico.query.order_by(Diagnostico.descripcion).all()
    tratamientos_catalogo = Tratamiento.query.order_by(Tratamiento.descripcion).all()
    
    if request.method == 'POST':
        motivo = request.form['motivo']
        observaciones = request.form.get('observaciones')
        
        selected_diag_ids = request.form.getlist('diagnosticos_seleccionados')
        selected_diagnosticos = []
        if selected_diag_ids:
            selected_diagnosticos = Diagnostico.query.filter(Diagnostico.id.in_([int(id_str) for id_str in selected_diag_ids])).all()

        selected_trat_ids = request.form.getlist('tratamientos_seleccionados')
        selected_tratamientos = []
        if selected_trat_ids:
            selected_tratamientos = Tratamiento.query.filter(Tratamiento.id.in_([int(id_str) for id_str in selected_trat_ids])).all()

        nueva_historia_obj = HistoriaClinica(
            motivo=motivo,
            observaciones=observaciones,
            paciente_id=paciente.id
        )
        
        db.session.add(nueva_historia_obj)
        
        nueva_historia_obj.diagnosticos = selected_diagnosticos
        nueva_historia_obj.tratamientos = selected_tratamientos
        
        try:
            db.session.commit() 
            flash('Historia creada correctamente.', 'success')
            return redirect(url_for('listar_historias', paciente_id=paciente.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la historia: {e}', 'danger')
            
    return render_template('nueva_historia.html', paciente=paciente, diagnosticos_catalogo=diagnosticos_catalogo, tratamientos_catalogo=tratamientos_catalogo)

@app.route('/historias/<int:id>')
@login_required
def ver_historia(id):
    historia = HistoriaClinica.query.get_or_404(id)
    return render_template('ver_historia.html', historia=historia)


@app.route('/pacientes/<int:paciente_id>/historias/<int:historia_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_historia(paciente_id, historia_id): 
    historia = HistoriaClinica.query.get_or_404(historia_id)
    paciente = Paciente.query.get_or_404(historia.paciente_id) 
    diagnosticos_catalogo = Diagnostico.query.order_by(Diagnostico.descripcion).all()
    tratamientos_catalogo = Tratamiento.query.order_by(Tratamiento.descripcion).all()

    if request.method == 'POST':
        historia.motivo = request.form['motivo']
        historia.observaciones = request.form.get('observaciones')
        
        selected_diag_ids = request.form.getlist('diagnosticos_seleccionados')
        selected_diagnosticos = []
        if selected_diag_ids:
            selected_diagnosticos = Diagnostico.query.filter(Diagnostico.id.in_([int(id_str) for id_str in selected_diag_ids])).all()
        historia.diagnosticos = selected_diagnosticos
        
        selected_trat_ids = request.form.getlist('tratamientos_seleccionados')
        selected_tratamientos = []
        if selected_trat_ids:
            selected_tratamientos = Tratamiento.query.filter(Tratamiento.id.in_([int(id_str) for id_str in selected_trat_ids])).all()
        historia.tratamientos = selected_tratamientos
        
        try:
            db.session.commit()
            flash('Historia clínica actualizada correctamente.', 'success')
            return redirect(url_for('listar_historias', paciente_id=historia.paciente_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error al actualizar la historia clínica: {e}', 'danger')
            
    return render_template('editar_historia.html', historia=historia, paciente=paciente, diagnosticos_catalogo=diagnosticos_catalogo, tratamientos_catalogo=tratamientos_catalogo)


@app.route('/pacientes/<int:paciente_id>/historias/<int:historia_id>/eliminar', methods=['POST'])
@login_required
def eliminar_historia(paciente_id, historia_id):
    historia = HistoriaClinica.query.get_or_404(historia_id)
    try:
        db.session.delete(historia)
        db.session.commit()
        flash('Historia clínica eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocurrió un error al eliminar la historia clínica: {e}', 'danger')
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
            flash('Formato de fecha y hora inválido. Use YYYY-MM-DDTHH:MM.', 'danger')
            return render_template('nueva_cita.html', paciente=paciente, cita=None)

        nueva = Cita(paciente_id=paciente.id, fecha_hora=fecha_hora, motivo=motivo, notas=notas)
        db.session.add(nueva)
        db.session.commit()
        flash('Cita creada correctamente.', 'success')
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
            flash('Formato de fecha y hora inválido. Use YYYY-MM-DDTHH:MM.', 'danger')
            return render_template('nueva_cita.html', cita=cita, paciente=paciente)

        cita.motivo = request.form['motivo']
        cita.notas = request.form.get('notas')
        db.session.commit()
        flash('Cita actualizada correctamente.', 'success')
        return redirect(url_for('ver_cita', cita_id=cita.id))
    return render_template('nueva_cita.html', cita=cita, paciente=paciente)


@app.route('/citas/<int:cita_id>/eliminar', methods=['POST'])
@login_required
def eliminar_cita(cita_id):
    cita = Cita.query.get_or_404(cita_id)
    paciente_id = cita.paciente_id
    db.session.delete(cita)
    db.session.commit()
    flash('Cita eliminada correctamente.', 'success')
    paciente = Paciente.query.get(paciente_id)
    if paciente:
        return redirect(url_for('listar_citas_paciente', paciente_id=paciente_id))
    else:
        return redirect(url_for('citas'))

# --- ICD Search Route ---
@app.route('/diagnosticos/buscar_icd') # Defaults to GET requests
@login_required
def buscar_icd_api():
    search_term = request.args.get('q', '').strip() # Get search term, strip whitespace

    if not search_term or len(search_term) < 2: # Basic validation for search term length
        return jsonify([]) # Return empty list if term is too short or empty
    
    # Assuming search_icd_codes handles its own errors and returns [] on failure
    results = search_icd_codes(search_term)
    
    # The results from search_icd_codes are already in a list of dicts format
    # e.g., [{'id': 'http://id.who.int/icd/entity/123', 'label': 'Some Disease'}]
    return jsonify(results)

# --- Diagnosticos Catalog Routes ---
@app.route('/diagnosticos')
@login_required
def diagnosticos_list():
    diagnosticos = Diagnostico.query.order_by(Diagnostico.codigo).all()
    return render_template('diagnosticos.html', diagnosticos=diagnosticos)

@app.route('/diagnosticos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_diagnostico():
    if request.method == 'POST':
        codigo = request.form['codigo']
        descripcion = request.form['descripcion']
        
        if Diagnostico.query.filter_by(codigo=codigo).first():
            flash('El código de diagnóstico ya existe.', 'danger')
            return render_template('nuevo_diagnostico.html', diagnostico=None, codigo=codigo, descripcion=descripcion)

        nuevo = Diagnostico(codigo=codigo, descripcion=descripcion)
        db.session.add(nuevo)
        try:
            db.session.commit()
            flash('Diagnóstico creado correctamente.', 'success')
            return redirect(url_for('diagnosticos_list'))
        except IntegrityError: 
            db.session.rollback()
            flash('Error: El código de diagnóstico ya existe o hubo un problema.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado: {e}', 'danger')
        
    return render_template('nuevo_diagnostico.html', diagnostico=None)

@app.route('/diagnosticos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_diagnostico(id):
    diag = Diagnostico.query.get_or_404(id)
    if request.method == 'POST':
        nuevo_codigo = request.form['codigo']
        nueva_descripcion = request.form['descripcion']

        if nuevo_codigo != diag.codigo and Diagnostico.query.filter_by(codigo=nuevo_codigo).first():
            flash('El nuevo código de diagnóstico ya está en uso por otro diagnóstico.', 'danger')
            return render_template('nuevo_diagnostico.html', diagnostico=diag)

        diag.codigo = nuevo_codigo
        diag.descripcion = nueva_descripcion
        try:
            db.session.commit()
            flash('Diagnóstico actualizado correctamente.', 'success')
            return redirect(url_for('diagnosticos_list'))
        except IntegrityError: 
            db.session.rollback()
            flash('Error: El código de diagnóstico ya existe o hubo un problema con la actualización.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado: {e}', 'danger')
            
    return render_template('nuevo_diagnostico.html', diagnostico=diag)

@app.route('/diagnosticos/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_diagnostico(id):
    diag = Diagnostico.query.get_or_404(id)
    if diag.historias_clinicas_associated.count() > 0:
        flash('No se puede eliminar el diagnóstico porque está asociado a una o más historias clínicas.', 'danger')
        return redirect(url_for('diagnosticos_list'))
    
    try:
        db.session.delete(diag)
        db.session.commit()
        flash('Diagnóstico eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el diagnóstico: {e}', 'danger')
    return redirect(url_for('diagnosticos_list'))

# --- Tratamientos Catalog Routes ---
@app.route('/tratamientos')
@login_required
def tratamientos_list():
    tratamientos = Tratamiento.query.order_by(Tratamiento.codigo).all()
    return render_template('tratamientos.html', tratamientos=tratamientos)

@app.route('/tratamientos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_tratamiento():
    if request.method == 'POST':
        codigo = request.form['codigo']
        descripcion = request.form['descripcion']
        costo_str = request.form.get('costo') 
        
        costo = None
        if costo_str: 
            try:
                costo = float(costo_str) 
            except ValueError:
                flash('Costo inválido. Debe ser un número.', 'danger')
                return render_template('nuevo_tratamiento.html', tratamiento=None, codigo=codigo, descripcion=descripcion, costo_str=costo_str)
        
        if Tratamiento.query.filter_by(codigo=codigo).first():
            flash('El código de tratamiento ya existe.', 'danger')
            return render_template('nuevo_tratamiento.html', tratamiento=None, codigo=codigo, descripcion=descripcion, costo_str=costo_str)

        nuevo = Tratamiento(codigo=codigo, descripcion=descripcion, costo=costo)
        db.session.add(nuevo)
        try:
            db.session.commit()
            flash('Tratamiento creado correctamente.', 'success')
            return redirect(url_for('tratamientos_list'))
        except IntegrityError:
            db.session.rollback()
            flash('Error: El código de tratamiento ya existe.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado: {e}', 'danger')
    return render_template('nuevo_tratamiento.html', tratamiento=None)

@app.route('/tratamientos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_tratamiento(id):
    trat = Tratamiento.query.get_or_404(id)
    if request.method == 'POST':
        nuevo_codigo = request.form['codigo']
        nueva_descripcion = request.form['descripcion']
        costo_str = request.form.get('costo')

        costo = None
        if costo_str:
            try:
                costo = float(costo_str) 
            except ValueError:
                flash('Costo inválido. Debe ser un número.', 'danger')
                return render_template('nuevo_tratamiento.html', tratamiento=trat)
        
        if nuevo_codigo != trat.codigo and Tratamiento.query.filter_by(codigo=nuevo_codigo).first():
            flash('El nuevo código de tratamiento ya está en uso.', 'danger')
            return render_template('nuevo_tratamiento.html', tratamiento=trat)

        trat.codigo = nuevo_codigo
        trat.descripcion = nueva_descripcion
        trat.costo = costo
        try:
            db.session.commit()
            flash('Tratamiento actualizado correctamente.', 'success')
            return redirect(url_for('tratamientos_list'))
        except IntegrityError:
            db.session.rollback()
            flash('Error: El código de tratamiento ya existe o hubo un problema.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado: {e}', 'danger')
    return render_template('nuevo_tratamiento.html', tratamiento=trat)

@app.route('/tratamientos/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_tratamiento(id):
    trat = Tratamiento.query.get_or_404(id)
    if trat.historias_clinicas_con_tratamiento.count() > 0: 
        flash('No se puede eliminar el tratamiento, está asociado a historias clínicas.', 'danger')
        return redirect(url_for('tratamientos_list'))
    
    try:
        db.session.delete(trat)
        db.session.commit()
        flash('Tratamiento eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el tratamiento: {e}', 'danger')
    return redirect(url_for('tratamientos_list'))

# --- Invoice Routes ---
@app.route('/facturas')
@login_required
def facturas_list():
    invoices = Factura.query.order_by(Factura.fecha_emision.desc()).all()
    return render_template('facturas.html', invoices=invoices)

@app.route('/pacientes/<int:paciente_id>/facturas')
@login_required
def facturas_paciente_list(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    invoices = paciente.facturas.order_by(Factura.fecha_emision.desc()).all()
    return render_template('paciente_facturas.html', paciente=paciente, invoices=invoices)

@app.route('/pacientes/<int:paciente_id>/facturas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_factura_paciente(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    if request.method == 'POST':
        fecha_vencimiento_str = request.form.get('fecha_vencimiento')
        fecha_vencimiento = None
        if fecha_vencimiento_str:
            try:
                fecha_vencimiento = datetime.strptime(fecha_vencimiento_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de fecha de vencimiento inválido. Use YYYY-MM-DD.', 'danger')
                return render_template('nueva_factura_form.html', paciente=paciente)

        nueva_factura = Factura(
            paciente_id=paciente.id,
            numero_factura=get_next_invoice_number(),
            fecha_vencimiento=fecha_vencimiento
        )
        db.session.add(nueva_factura)
        try:
            db.session.commit()
            flash('Factura creada. Ahora puede agregar ítems.', 'success')
            return redirect(url_for('ver_factura', factura_id=nueva_factura.id)) 
        except IntegrityError as e:
            db.session.rollback()
            flash(f'Error al crear la factura: Ya existe una factura con ese número o hubo otro problema de integridad. {e}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado al crear la factura: {e}', 'danger')
        
    return render_template('nueva_factura_form.html', paciente=paciente)

@app.route('/facturas/<int:factura_id>', methods=['GET']) 
@login_required
def ver_factura(factura_id):
    factura = Factura.query.get_or_404(factura_id)
    tratamientos_catalogo = Tratamiento.query.order_by(Tratamiento.descripcion).all() 
    return render_template('ver_factura.html', factura=factura, tratamientos_catalogo=tratamientos_catalogo)

@app.route('/facturas/<int:factura_id>/items/agregar', methods=['POST'])
@login_required
def agregar_item_factura(factura_id):
    factura = Factura.query.get_or_404(factura_id)
    
    try:
        descripcion = request.form['descripcion']
        cantidad_str = request.form['cantidad']
        precio_unitario_str = request.form['precio_unitario']
        tratamiento_id_str = request.form.get('tratamiento_id')

        if not descripcion:
            flash('La descripción del ítem es obligatoria.', 'danger')
            return redirect(url_for('ver_factura', factura_id=factura.id))

        cantidad = int(cantidad_str)
        precio_unitario = float(precio_unitario_str) 
        
        if cantidad <= 0 or precio_unitario < 0:
            flash('Cantidad debe ser positiva y precio unitario no negativo.', 'danger')
            return redirect(url_for('ver_factura', factura_id=factura.id))

        tratamiento_id = None
        if tratamiento_id_str and tratamiento_id_str != "":
            tratamiento_id = int(tratamiento_id_str)

        nuevo_item = ItemFactura(
            factura_id=factura.id,
            descripcion=descripcion,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            tratamiento_id=tratamiento_id
        )
        nuevo_item.calculate_subtotal() 
        
        db.session.add(nuevo_item)
        db.session.commit() 
        
        calculate_and_update_invoice_total(factura.id) 
        flash('Ítem agregado a la factura.', 'success')

    except ValueError:
        flash('Cantidad y Precio Unitario deben ser números válidos.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al agregar ítem: {e}', 'danger')
        
    return redirect(url_for('ver_factura', factura_id=factura.id))

@app.route('/facturas/items/<int:item_id>/eliminar', methods=['POST'])
@login_required
def eliminar_item_factura(item_id):
    item = ItemFactura.query.get_or_404(item_id)
    factura_id = item.factura_id
    
    try:
        db.session.delete(item)
        db.session.commit()
        calculate_and_update_invoice_total(factura_id) 
        flash('Ítem eliminado de la factura.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar ítem: {e}', 'danger')
        
    return redirect(url_for('ver_factura', factura_id=factura_id))

@app.route('/facturas/<int:factura_id>/marcar_pagada', methods=['POST'])
@login_required
def marcar_factura_pagada(factura_id):
    factura = Factura.query.get_or_404(factura_id)
    if factura.estado == 'Pendiente': # Or any other states from which it can be marked paid
        factura.estado = 'Pagada'
        try:
            db.session.add(factura) # Ensure it's in session
            db.session.commit()
            flash('Factura marcada como Pagada.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar estado de la factura: {e}', 'danger')
    else:
        flash('La factura no está en un estado que permita marcarla como pagada directamente.', 'warning')
    return redirect(url_for('ver_factura', factura_id=factura.id))

# Aquí puedes añadir más rutas y lógica para tu aplicación

@app.route('/diagnosticos/chapters')
@login_required # Ensure user is logged in
def list_icd_chapters():
    # Route to list ICD chapters
    # The release_uri is no longer used as data is sourced locally.
    chapters_data, status = get_icd_chapters()

    chapters_for_template = []
    if status == "SUCCESS":
        if chapters_data:
            for chapter in chapters_data:
                chapter_title = "Unknown Title"
                if chapter and chapter.get('title'):
                    if isinstance(chapter.get('title'), dict):
                        chapter_title = chapter['title'].get('@value', chapter_title)
                    elif isinstance(chapter.get('title'), str):
                        chapter_title = chapter['title']

                chapter_id = "Unknown ID"
                if chapter:
                    chapter_id = chapter.get('@id', chapter.get('id', chapter_id))

                chapter_class_kind = "N/A"
                if chapter:
                    chapter_class_kind = chapter.get('classKind', 'N/A')

                chapters_for_template.append({
                    'id': chapter_id,
                    'title': chapter_title,
                    'classKind': chapter_class_kind
                })
    # Removed specific credential/token error messages as we are using local data.
    # The local_icd_service and underlying file operations will return different statuses
    # like "LOCAL_CHAPTERS_ERROR_OR_NO_DATA", "FILE_NOT_FOUND", etc.
    # The generic message below should cover these.
    elif status != "SUCCESS": # Catch any non-SUCCESS status
        flash(f"Error al obtener los capítulos de CIE: {status}. Verifique la disponibilidad y formato del archivo 'structured_icd_data.json'.", "danger")

    return render_template('list_chapters.html', chapters=chapters_for_template) # Removed release_uri from context

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
