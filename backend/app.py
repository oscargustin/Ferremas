# Archivo: backend/app.py
import os
import time
import json
import queue
import requests 
from flask import Flask, request, jsonify, Response, stream_with_context, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError # Importar para manejar errores de SQLAlchemy
from transbank.webpay.webpay_plus.transaction import Transaction # Para Webpay Plus
from transbank.common.options import WebpayOptions # Para configurar opciones
from transbank.common.integration_type import IntegrationType 

app = Flask(__name__,
            static_folder='../frontend/static', # ¡Ruta CORREGIDA!
            template_folder='../frontend/templates') # ¡Ruta CORREGIDA!
CORS(app)

# --- Configuración de la Base de Datos PostgreSQL ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://ferremas_user:password123@localhost:5432/ferremasbd')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- IMPRIMIR LA URL DE LA BASE DE DATOS QUE SE ESTÁ USANDO (PARA DEPURACIÓN) ---
print(f"DEBUG: SQLAlchemy DB URI being used: {app.config['SQLALCHEMY_DATABASE_URI']}")
# -------------------------------------------------------------------------------

db = SQLAlchemy(app)

EXCHANGE_RATE_API_KEY = "fe1b0b877cfcfd563b220ca7" 
EXCHANGE_RATE_API_BASE_URL = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/CLP" # Solicita el tipo de cambio más reciente para CLP


# --- Configuración de Transbank (¡NUEVO!) ---
# Estas credenciales son de EJEMPLO para el ambiente de integración (sandbox).
# Debes reemplazarlas con las que obtengas de Transbank Developers.
# Las credenciales reales deben ser guardadas de forma segura (ej. variables de entorno).
TRANSBANK_COMMERCE_CODE = os.environ.get('TRANSBANK_COMMERCE_CODE', '597055555532') 
TRANSBANK_API_KEY = os.environ.get('TRANSBANK_API_KEY', '579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C') 
TRANSBANK_ENVIRONMENT = IntegrationType.TEST # O IntegrationType.LIVE para producción

# Inicializar Transbank Webpay Plus Transaction
# Es crucial configurar las opciones de Webpay con tus credenciales
webpay_transaction = Transaction(WebpayOptions(
    TRANSBANK_COMMERCE_CODE,
    TRANSBANK_API_KEY,
    TRANSBANK_ENVIRONMENT
))

# --- Definición de Modelos (el resto de tus modelos Sucursal, Producto, ProductoSucursal) ---
class Sucursal(db.Model):
    __tablename__ = 'sucursales'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=True)
    productos_sucursales = db.relationship('ProductoSucursal', backref='sucursal', lazy=True)
    def to_dict(self):
        return {'id': self.id, 'nombre': self.nombre, 'direccion': self.direccion}

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    marca = db.Column(db.String(100), nullable=True)
    sucursales_info = db.relationship('ProductoSucursal', backref='producto', lazy=True)
    def to_dict(self):
        return {'id': self.id, 'nombre': self.nombre, 'marca': self.marca}

class ProductoSucursal(db.Model):
    __tablename__ = 'productos_sucursales'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursales.id'), nullable=False)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('producto_id', 'sucursal_id', name='_producto_sucursal_uc'),)
    def to_dict(self):
        return {'id': self.id, 'producto_id': self.producto_id, 'sucursal_id': self.sucursal_id, 'precio': float(self.precio), 'stock': self.stock}

# --- Implementación de Server-Sent Events (SSE) ---
clients = []
def format_sse(data: str, event=None) -> str:
    msg = f'data: {data}\n\n'
    if event is not None:
        msg = f'event: {event}\n{msg}'
    return msg

def notify_clients(data: dict, event=None):
    message = format_sse(json.dumps(data), event)
    disconnected_clients = []
    for client_queue in list(clients):
        try:
            client_queue.put_nowait(message)
        except queue.Full:
            disconnected_clients.append(client_queue)
        except Exception as e:
            print(f"Error sending message to client: {e}")
            disconnected_clients.append(client_queue)
    for client_queue in disconnected_clients:
        if client_queue in clients:
            clients.remove(client_queue)
            print("Client disconnected and removed.")

# --- Definición de Rutas ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/productos/buscar', methods=['GET'])
def buscar_productos():
    query = request.args.get('q')
    if not query:
        return jsonify({"message": "Missing search query"}), 400
    try:
        product_id_query = int(query)
        productos = Producto.query.filter(
            or_(Producto.id == product_id_query, Producto.nombre.ilike(f'%{query}%'))
        ).all()
    except ValueError:
        productos = Producto.query.filter(Producto.nombre.ilike(f'%{query}%')).all()
    if not productos:
        return jsonify({"message": "No products found", "results": []}), 404
    results = []
    for producto in productos:
        producto_data = producto.to_dict()
        sucursales_info = []
        productos_sucursales = ProductoSucursal.query.filter_by(producto_id=producto.id).all()
        for ps in productos_sucursales:
            sucursal = Sucursal.query.get(ps.sucursal_id)
            if sucursal:
                 sucursales_info.append({
                     "sucursal_id": sucursal.id,
                     "nombre": sucursal.nombre,
                     "precio": float(ps.precio),
                     "stock": ps.stock
                 })
        producto_data['sucursales_info'] = sucursales_info
        results.append(producto_data)
    return jsonify(results), 200

@app.route('/api/exchange_rate', methods=['GET'])
def get_exchange_rate():
    try:
        # Hacer la solicitud a la API externa
        response = requests.get(EXCHANGE_RATE_API_BASE_URL)
        response.raise_for_status() # Lanza una excepción para errores HTTP (4xx o 5xx)
        data = response.json()

        exchange_rate_usd = data['conversion_rates']['USD']

        rate_usd_to_clp = 1 / exchange_rate_usd


        print(f"DEBUG: Tasa de cambio obtenida (1 USD = {rate_usd_to_clp:.2f} CLP)")
        return jsonify({"rate": round(rate_usd_to_clp, 2)}), 200 
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con la API de tipo de cambio: {e}")
        return jsonify({"message": "Error al conectar con el servicio de tipo de cambio", "error": str(e)}), 500
    except KeyError as e:
        print(f"Error al parsear la respuesta de la API (clave no encontrada): {e}. Respuesta completa: {data}")
        return jsonify({"message": "Error al procesar la respuesta del tipo de cambio", "error": f"Clave no encontrada: {e}"}), 500
    except Exception as e:
        print(f"Error inesperado al obtener el tipo de cambio: {e}")
        return jsonify({"message": "Error interno al obtener el tipo de cambio", "error": str(e)}), 500
    
    
@app.route('/api/venta', methods=['POST'])
def procesar_venta():
    data = request.json
    producto_id = data.get('product_id')
    sucursal_id = data.get('branch_id')
    cantidad = data.get('quantity')
    if not all([producto_id, sucursal_id, cantidad is not None]):
        return jsonify({"message": "Missing required data (product_id, branch_id, quantity)"}), 400
    try:
        producto_id = int(producto_id)
        sucursal_id = int(sucursal_id)
        cantidad = int(cantidad)
        if cantidad <= 0:
             return jsonify({"message": "Quantity must be a positive number (minimum 1)"}), 400
    except ValueError:
        return jsonify({"message": "Invalid data types (product_id, branch_id, quantity must be integers)"}), 400
    try:
        producto_sucursal = ProductoSucursal.query.filter_by(
            producto_id=producto_id,
            sucursal_id=sucursal_id
        ).with_for_update().first()
        if not producto_sucursal:
            db.session.rollback()
            return jsonify({"message": "Product not found in this branch"}), 404
        if cantidad > producto_sucursal.stock:
            db.session.rollback()
            return jsonify({"message": "Insufficient stock", "available_stock": producto_sucursal.stock}), 400
        producto_sucursal.stock -= cantidad
        low_stock_threshold = 5
        if producto_sucursal.stock <= low_stock_threshold:
             producto = Producto.query.get(producto_id)
             sucursal = Sucursal.query.get(sucursal_id)
             product_name = producto.nombre if producto else 'Unknown Product'
             branch_name = sucursal.nombre if sucursal else 'Unknown Branch'
             notification_data = {
                 "product_id": producto_id,
                 "branch_id": sucursal_id,
                 "product_name": product_name,
                 "branch_name": branch_name,
                 "current_stock": producto_sucursal.stock
             }
             notify_clients(notification_data, event='low_stock_alert')
             print(f"Low stock alert sent for Product ID {producto_id} at Branch ID {sucursal_id}. Stock: {producto_sucursal.stock}")
        db.session.commit()
        producto = Producto.query.get(producto_id)
        sucursal = Sucursal.query.get(sucursal_id)
        product_name = producto.nombre if producto else 'Unknown Product'
        branch_name = sucursal.nombre if sucursal else 'Unknown Branch'
        return jsonify({
            "message": "Sale processed successfully",
            "new_stock": producto_sucursal.stock,
            "product_name": product_name,
            "branch_name": branch_name
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error processing sale: {e}")
        return jsonify({"message": "An error occurred while processing the sale", "error": str(e)}), 500

@app.route('/events/low-stock')
def low_stock_events():
    client_queue = queue.Queue()
    clients.append(client_queue)
    print("New SSE client connected.")
    @stream_with_context
    def event_stream():
        while True:
            try:
                message = client_queue.get(timeout=1.0)
                yield message
            except queue.Empty:
                yield ': keepalive\n\n'
            except Exception as e:
                print(f"Error in SSE stream for a client: {e}")
                break
        if client_queue in clients:
            clients.remove(client_queue)
            print("SSE client disconnected.")
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    # --- BLOQUE DE INICIALIZACIÓN ---
    with app.app_context():
        print("DEBUG: Attempting to create database tables...")
        try:
            db.create_all()
            print("DEBUG: Database tables created successfully (or already exist).")

            # TODO: Opcional: Añadir datos de ejemplo si la base de datos está vacía
            # Puedes usar este bloque para poblar tu DB con datos de prueba
            # Descomenta y ajusta si necesitas insertar datos iniciales
            if not Sucursal.query.first():
                print("Adding sample data...")
                sucursal1 = Sucursal(nombre='Sucursal Centro', direccion='Calle Falsa 123')
                sucursal2 = Sucursal(nombre='Casa Matriz', direccion='Avenida Siempre Viva 742')
                db.session.add_all([sucursal1, sucursal2])
                db.session.commit()
                print("Sample sucursales added.")
            
            if not Producto.query.first():
                 producto1 = Producto(nombre='Martillo', marca='ToolCo')
                 producto2 = Producto(nombre='Destornillador Phillips', marca='FixIt')
                 producto3 = Producto(nombre='Sierra', marca='CutMaster')
                 db.session.add_all([producto1, producto2, producto3])
                 db.session.commit()
                 print("Sample productos added.")
            
                 # Añadir stock y precio en sucursales (ejemplo)
                 # Asegúrate de que los IDs de sucursal y producto existan
                 # Stock bajo para Martillo en Sucursal Centro para probar SSE
                 # Puedes obtener los objetos recién creados o buscarlos por ID
                 s1 = Sucursal.query.filter_by(nombre='Sucursal Centro').first()
                 s2 = Sucursal.query.filter_by(nombre='Casa Matriz').first()
                 p1 = Producto.query.filter_by(nombre='Martillo').first()
                 p2 = Producto.query.filter_by(nombre='Destornillador Phillips').first()
                 p3 = Producto.query.filter_by(nombre='Sierra').first()
            
                 if s1 and s2 and p1 and p2 and p3:
                     ps1 = ProductoSucursal(producto=p1, sucursal=s1, precio=15000.00, stock=50) # Stock bajo
                     ps2 = ProductoSucursal(producto=p1, sucursal=s2, precio=10000.00, stock=50)
                     ps3 = ProductoSucursal(producto=p2, sucursal=s1, precio=20000.00, stock=50)
                     ps4 = ProductoSucursal(producto=p3, sucursal=s2, precio=19000.00, stock=50)
                     
                     
                     
                     
                     
                     
                     
                     
                     
                     
                     
                     db.session.add_all([ps1, ps2, ps3, ps4])
                     db.session.commit()
                     print("Sample ProductoSucursal data added.")
                 else:
                     print("WARNING: Could not add ProductoSucursal data, some parent records not found.")

        except SQLAlchemyError as e:
            print(f"ERROR: SQLAlchemy error during db.create_all(): {e}")
            # Puedes añadir sys.exit(1) aquí para que el programa termine si hay un error crítico
            # import sys
            # sys.exit(1)
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during initialization: {e}")
            # import sys
            # sys.exit(1)

    # Ejecutar la aplicación Flask
    # debug=True es solo para desarrollo
    # threaded=True es importante para SSE con esta implementación simple de colas
    print("DEBUG: Attempting to run Flask app...")
    app.run(debug=True, port=5000, threaded=True)

