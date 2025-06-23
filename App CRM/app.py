from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'

# Directorio para almacenar los archivos de campañas
CAMPAIGNS_DIR = 'campañas'
CAMPAIGNS_LIST_FILE = 'lista_campañas.txt'

def ensure_campaigns_dir():
    """Asegurar que el directorio de campañas existe"""
    if not os.path.exists(CAMPAIGNS_DIR):
        os.makedirs(CAMPAIGNS_DIR)

def get_campaign_file_path(campaign_name):
    """Obtener la ruta del archivo para una campaña específica"""
    safe_name = "".join(c for c in campaign_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_name = safe_name.replace(' ', '_')
    return os.path.join(CAMPAIGNS_DIR, f'{safe_name}.xlsx')

def load_campaigns_list():
    """Cargar la lista de campañas existentes"""
    ensure_campaigns_dir()
    campaigns_file = os.path.join(CAMPAIGNS_DIR, CAMPAIGNS_LIST_FILE)
    
    if os.path.exists(campaigns_file):
        with open(campaigns_file, 'r', encoding='utf-8') as f:
            campaigns = [line.strip() for line in f.readlines() if line.strip()]
    else:
        campaigns = []
    
    # Si no hay campañas, crear una por defecto
    if not campaigns:
        campaigns = ['Campaña Principal']
        save_campaigns_list(campaigns)
    
    return campaigns

def save_campaigns_list(campaigns):
    """Guardar la lista de campañas"""
    ensure_campaigns_dir()
    campaigns_file = os.path.join(CAMPAIGNS_DIR, CAMPAIGNS_LIST_FILE)
    
    with open(campaigns_file, 'w', encoding='utf-8') as f:
        for campaign in campaigns:
            f.write(f'{campaign}\n')

def load_data(campaign_name):
    """Cargar datos del archivo Excel de una campaña específica"""
    try:
        file_path = get_campaign_file_path(campaign_name)
        
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            # Asegurar que las columnas necesarias existan
            required_columns = ["Nombre", "Cedula", "Telefono", "Telefono2", "Estatus", "Comentario", "FechaActualizacion"]
            for col in required_columns:
                if col not in df.columns:
                    if col == "FechaActualizacion":
                        df[col] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        df[col] = ""
            # Convertir valores NaN a string vacío
            df = df.fillna("")
            return df
        else:
            # Crear DataFrame vacío
            df = pd.DataFrame(columns=["Nombre", "Cedula", "Telefono", "Telefono2", "Estatus", "Comentario", "FechaActualizacion"])
            df.to_excel(file_path, index=False)
            return df
    except Exception as e:
        print(f"Error cargando datos para {campaign_name}: {e}")
        return pd.DataFrame(columns=["Nombre", "Cedula", "Telefono", "Telefono2", "Estatus", "Comentario", "FechaActualizacion"])

def save_data(df, campaign_name):
    """Guardar datos al archivo Excel de una campaña específica"""
    try:
        file_path = get_campaign_file_path(campaign_name)
        df.to_excel(file_path, index=False)
        return True
    except Exception as e:
        print(f"Error guardando datos para {campaign_name}: {e}")
        return False

@app.route('/')
def select_campaign():
    """Página principal para seleccionar campaña"""
    campaigns = load_campaigns_list()
    return render_template('select_campaign.html', campaigns=campaigns)

@app.route('/campaign/<campaign_name>')
def campaign_index(campaign_name):
    """Página principal de una campaña específica"""
    if campaign_name not in load_campaigns_list():
        flash(f'La campaña "{campaign_name}" no existe', 'error')
        return redirect(url_for('select_campaign'))
    
    query = request.args.get('query', '').strip()
    estatus_filter = request.args.get('estatus_filter', '')
    
    df = load_data(campaign_name)
    filtered_df = df.copy()

    # Aplicar filtros
    if query:
        filtered_df = df[df.apply(lambda row:
            query.lower() in str(row['Nombre']).lower() or
            query.lower() in str(row['Cedula']).lower() or
            query.lower() in str(row['Telefono']).lower() or
            query.lower() in str(row['Telefono2']).lower() or
            query.lower() in str(row['Comentario']).lower(), axis=1)]
    
    if estatus_filter and estatus_filter != '':
        filtered_df = filtered_df[filtered_df['Estatus'] == estatus_filter]

    # Calcular estadísticas
    stats = {
        'total': len(df),
        'pendientes': len(df[df['Estatus'] == 'Pendiente']),
        'llamados': len(df[df['Estatus'] == 'Llamado']),
        'elegibles': len(df[df['Estatus'] == 'Elegible']),
        'no_elegibles': len(df[df['Estatus'] == 'No Elegible']),
        'NoTieneWhatsapp': len(df[df['Estatus'] == 'No Tiene Whatsapp'])
    }

    return render_template('campaign_index.html', 
                         data=filtered_df.to_dict(orient='records'), 
                         query=query,
                         estatus_filter=estatus_filter,
                         stats=stats,
                         campaign_name=campaign_name,
                         campaigns=load_campaigns_list())

@app.route('/campaign/<campaign_name>/edit', methods=['POST'])
def edit_record(campaign_name):
    """Editar un registro de una campaña específica"""
    if campaign_name not in load_campaigns_list():
        flash(f'La campaña "{campaign_name}" no existe', 'error')
        return redirect(url_for('select_campaign'))
    
    try:
        cedula = request.form['Cedula'].strip()
        estatus = request.form['Estatus']
        comentario = request.form['Comentario'].strip()
        
        # Capturar los parámetros de filtro para redirigir
        query = request.form.get('query', '')
        estatus_filter = request.form.get('estatus_filter', '')

        if not cedula:
            flash('Error: Cédula no puede estar vacía', 'error')
            return redirect(url_for('campaign_index', campaign_name=campaign_name, query=query, estatus_filter=estatus_filter))

        df = load_data(campaign_name)
        
        # Verificar que la cédula existe
        if cedula not in df['Cedula'].values:
            flash(f'Error: No se encontró registro con cédula {cedula}', 'error')
            return redirect(url_for('campaign_index', campaign_name=campaign_name, query=query, estatus_filter=estatus_filter))

        # Actualizar datos
        mask = df['Cedula'] == cedula
        df.loc[mask, 'Estatus'] = estatus
        df.loc[mask, 'Comentario'] = comentario
        df.loc[mask, 'FechaActualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if save_data(df, campaign_name):
            flash(f'Registro actualizado exitosamente', 'success')
        else:
            flash('Error al guardar los cambios', 'error')

    except Exception as e:
        print(f"Error en edit: {e}")
        flash('Error inesperado al actualizar el registro', 'error')
        query = request.form.get('query', '')
        estatus_filter = request.form.get('estatus_filter', '')

    return redirect(url_for('campaign_index', campaign_name=campaign_name, query=query, estatus_filter=estatus_filter))

@app.route('/campaign/<campaign_name>/add', methods=['GET', 'POST'])
def add_record(campaign_name):
    """Agregar un registro a una campaña específica"""
    if campaign_name not in load_campaigns_list():
        flash(f'La campaña "{campaign_name}" no existe', 'error')
        return redirect(url_for('select_campaign'))
    
    if request.method == 'POST':
        try:
            nombre = request.form['Nombre'].strip()
            cedula = request.form['Cedula'].strip()
            telefono = request.form['Telefono'].strip()
            telefono2 = request.form['Telefono2'].strip()
            
            # Validaciones
            if not all([nombre, cedula, telefono]):
                flash('Error: Nombre, cédula y teléfono principal son obligatorios', 'error')
                return render_template('add_record.html', campaign_name=campaign_name, campaigns=load_campaigns_list())
            
            df = load_data(campaign_name)
            
            # Verificar que la cédula no exista
            if cedula in df['Cedula'].values:
                flash(f'Error: Ya existe un registro con la cédula {cedula}', 'error')
                return render_template('add_record.html', campaign_name=campaign_name, campaigns=load_campaigns_list())
            
            # Agregar nuevo registro
            new_row = {
                'Nombre': nombre,
                'Cedula': cedula,
                'Telefono': telefono,
                'Telefono2': telefono2,
                'Estatus': 'Pendiente',
                'Comentario': '',
                'FechaActualizacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            if save_data(df, campaign_name):
                flash(f'Registro agregado exitosamente: {nombre}', 'success')
                return redirect(url_for('campaign_index', campaign_name=campaign_name))
            else:
                flash('Error al guardar el nuevo registro', 'error')
                
        except Exception as e:
            print(f"Error en add: {e}")
            flash('Error inesperado al agregar el registro', 'error')
    
    return render_template('add_record.html', campaign_name=campaign_name, campaigns=load_campaigns_list())

@app.route('/campaign/<campaign_name>/delete/<cedula>', methods=['POST'])
def delete_record(campaign_name, cedula):
    """Eliminar un registro de una campaña específica"""
    if campaign_name not in load_campaigns_list():
        flash(f'La campaña "{campaign_name}" no existe', 'error')
        return redirect(url_for('select_campaign'))
    
    try:
        # Capturar los parámetros de filtro para redirigir
        query = request.form.get('query', '')
        estatus_filter = request.form.get('estatus_filter', '')
        
        df = load_data(campaign_name)
        
        if cedula not in df['Cedula'].values:
            flash(f'Error: No se encontró registro con cédula {cedula}', 'error')
            return redirect(url_for('campaign_index', campaign_name=campaign_name, query=query, estatus_filter=estatus_filter))
        
        # Eliminar registro
        df = df[df['Cedula'] != cedula]
        
        if save_data(df, campaign_name):
            flash(f'Registro eliminado exitosamente', 'success')
        else:
            flash('Error al eliminar el registro', 'error')
            
    except Exception as e:
        print(f"Error en delete: {e}")
        flash('Error inesperado al eliminar el registro', 'error')
        query = request.form.get('query', '')
        estatus_filter = request.form.get('estatus_filter', '')
    
    return redirect(url_for('campaign_index', campaign_name=campaign_name, query=query, estatus_filter=estatus_filter))

@app.route('/add_campaign', methods=['POST'])
def add_campaign():
    """Agregar una nueva campaña"""
    try:
        campaign_name = request.form['campaign_name'].strip()
        
        if not campaign_name:
            flash('Error: El nombre de la campaña no puede estar vacío', 'error')
            return redirect(url_for('select_campaign'))
        
        campaigns = load_campaigns_list()
        
        if campaign_name in campaigns:
            flash(f'Error: Ya existe una campaña con el nombre "{campaign_name}"', 'error')
            return redirect(url_for('select_campaign'))
        
        # Agregar nueva campaña
        campaigns.append(campaign_name)
        save_campaigns_list(campaigns)
        
        # Crear el archivo Excel vacío para la nueva campaña
        df = pd.DataFrame(columns=["Nombre", "Cedula", "Telefono", "Telefono2", "Estatus", "Comentario", "FechaActualizacion"])
        save_data(df, campaign_name)
        
        flash(f'Campaña "{campaign_name}" creada exitosamente', 'success')
        return redirect(url_for('campaign_index', campaign_name=campaign_name))
        
    except Exception as e:
        print(f"Error creando campaña: {e}")
        flash('Error inesperado al crear la campaña', 'error')
        return redirect(url_for('select_campaign'))

@app.route('/delete_campaign/<campaign_name>', methods=['POST'])
def delete_campaign(campaign_name):
    """Eliminar una campaña completa"""
    try:
        campaigns = load_campaigns_list()
        
        if campaign_name not in campaigns:
            flash(f'Error: La campaña "{campaign_name}" no existe', 'error')
            return redirect(url_for('select_campaign'))
        
        if len(campaigns) <= 1:
            flash('Error: No puedes eliminar la última campaña', 'error')
            return redirect(url_for('select_campaign'))
        
        # Eliminar de la lista
        campaigns.remove(campaign_name)
        save_campaigns_list(campaigns)
        
        # Eliminar el archivo
        file_path = get_campaign_file_path(campaign_name)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        flash(f'Campaña "{campaign_name}" eliminada exitosamente', 'success')
        return redirect(url_for('select_campaign'))
        
    except Exception as e:
        print(f"Error eliminando campaña: {e}")
        flash('Error inesperado al eliminar la campaña', 'error')
        return redirect(url_for('select_campaign'))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)