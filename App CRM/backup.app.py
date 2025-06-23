from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'

# Ruta del archivo Excel
FILE_PATH = 'registro.xlsx'

def load_data():
    """Cargar datos del archivo Excel"""
    try:
        if os.path.exists(FILE_PATH):
            df = pd.read_excel(FILE_PATH)
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
            df.to_excel(FILE_PATH, index=False)
            return df
    except Exception as e:
        print(f"Error cargando datos: {e}")
        return pd.DataFrame(columns=["Nombre", "Cedula", "Telefono", "Telefono2", "Estatus", "Comentario", "FechaActualizacion"])

def save_data(df):
    """Guardar datos al archivo Excel"""
    try:
        df.to_excel(FILE_PATH, index=False)
        return True
    except Exception as e:
        print(f"Error guardando datos: {e}")
        return False

# Cargar datos al iniciar
df = load_data()

@app.route('/', methods=['GET', 'POST'])
def index():
    global df
    df = load_data()  # Recargar datos
    
    query = request.args.get('query', '').strip()
    estatus_filter = request.args.get('estatus_filter', '')
    
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

    return render_template('index.html', 
                         data=filtered_df.to_dict(orient='records'), 
                         query=query,
                         estatus_filter=estatus_filter,
                         stats=stats)

@app.route('/edit', methods=['POST'])
def edit():
    global df
    
    try:
        cedula = request.form['Cedula'].strip()
        estatus = request.form['Estatus']
        comentario = request.form['Comentario'].strip()
        
        # Capturar los parámetros de filtro para redirigir
        query = request.form.get('query', '')
        estatus_filter = request.form.get('estatus_filter', '')

        if not cedula:
            flash('Error: Cédula no puede estar vacía', 'error')
            return redirect(url_for('index', query=query, estatus_filter=estatus_filter))

        df = load_data()  # Recargar datos
        
        # Verificar que la cédula existe
        if cedula not in df['Cedula'].values:
            flash(f'Error: No se encontró registro con cédula {cedula}', 'error')
            return redirect(url_for('index', query=query, estatus_filter=estatus_filter))

        # Actualizar datos
        mask = df['Cedula'] == cedula
        df.loc[mask, 'Estatus'] = estatus
        df.loc[mask, 'Comentario'] = comentario
        df.loc[mask, 'FechaActualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if save_data(df):
            flash(f'Registro actualizado exitosamente', 'success')
        else:
            flash('Error al guardar los cambios', 'error')

    except Exception as e:
        print(f"Error en edit: {e}")
        flash('Error inesperado al actualizar el registro', 'error')
        query = request.form.get('query', '')
        estatus_filter = request.form.get('estatus_filter', '')

    return redirect(url_for('index', query=query, estatus_filter=estatus_filter))

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        global df
        
        try:
            nombre = request.form['Nombre'].strip()
            cedula = request.form['Cedula'].strip()
            telefono = request.form['Telefono'].strip()
            telefono2 = request.form['Telefono2'].strip()
            
            # Validaciones
            if not all([nombre, cedula, telefono]):
                flash('Error: Nombre, cédula y teléfono principal son obligatorios', 'error')
                return render_template('add.html')
            
            df = load_data()  # Recargar datos
            
            # Verificar que la cédula no exista
            if cedula in df['Cedula'].values:
                flash(f'Error: Ya existe un registro con la cédula {cedula}', 'error')
                return render_template('add.html')
            
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
            
            if save_data(df):
                flash(f'Registro agregado exitosamente: {nombre}', 'success')
                return redirect(url_for('index'))
            else:
                flash('Error al guardar el nuevo registro', 'error')
                
        except Exception as e:
            print(f"Error en add: {e}")
            flash('Error inesperado al agregar el registro', 'error')
    
    return render_template('add.html')

@app.route('/delete/<cedula>', methods=['POST'])
def delete(cedula):
    global df
    
    try:
        # Capturar los parámetros de filtro para redirigir
        query = request.form.get('query', '')
        estatus_filter = request.form.get('estatus_filter', '')
        
        df = load_data()
        
        if cedula not in df['Cedula'].values:
            flash(f'Error: No se encontró registro con cédula {cedula}', 'error')
            return redirect(url_for('index', query=query, estatus_filter=estatus_filter))
        
        # Eliminar registro
        df = df[df['Cedula'] != cedula]
        
        if save_data(df):
            flash(f'Registro eliminado exitosamente', 'success')
        else:
            flash('Error al eliminar el registro', 'error')
            
    except Exception as e:
        print(f"Error en delete: {e}")
        flash('Error inesperado al eliminar el registro', 'error')
        query = request.form.get('query', '')
        estatus_filter = request.form.get('estatus_filter', '')
    
    return redirect(url_for('index', query=query, estatus_filter=estatus_filter))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)