# Archivo: backend/app.py
import os
import time
import json
import queue
import requests
from datetime import datetime # Importar datetime aquí arriba

# Importar y cargar dotenv al principio de cada script que lo necesite
from dotenv import load_dotenv
load_dotenv() # Carga las variables de entorno desde .env

# Importaciones gRPC (solo cliente)
import grpc
import product_pb2
import product_pb2_grpc # Necesario para el stub del cliente gRPC

from flask import Flask, request, jsonify, Response, stream_with_context, render_template

# NOTA: Importa SQLAlchemy y CORS aquí mismo si no los tienes ya importados
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

# Importaciones de Transbank SDK
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType

app = Flask(__name__,
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
CORS(app)

# --- Configuración de la Base de Datos PostgreSQL ---
# Ahora lee DATABASE_URL desde el .env; si no existe, usa el valor por defecto
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://ferremas_user:password123@localhost:5432/ferremasbd')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"DEBUG (Flask App): SQLAlchemy DB URI being used: {app.config['SQLALCHEMY_DATABASE_URI']}")

db = SQLAlchemy(app)

# --- Configuración de la API de tipo de cambio ---
# Ahora lee EXCHANGE_RATE_API_KEY desde el .env
EXCHANGE_RATE_API_KEY = os.environ.get('EXCHANGE_RATE_API_KEY', 'fe1b0b877cfcfd563b220ca7')
EXCHANGE_RATE_API_BASE_URL = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/CLP"

# --- Configuración de Transbank ---
# Lee desde el .env con valores por defecto
TRANSBANK_COMMERCE_CODE = os.environ.get('TRANSBANK_COMMERCE_CODE', '597055555532')
TRANSBANK_API_KEY = os.environ.get('TRANSBANK_API_KEY', '579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C')
# CORREGIDO: Usar IntegrationType.TEST directamente
TRANSBANK_ENVIRONMENT = IntegrationType.TEST 

webpay_transaction = Transaction(WebpayOptions(
    TRANSBANK_COMMERCE_CODE,
    TRANSBANK_API_KEY,
    TRANSBANK_ENVIRONMENT
))

# --- Definición de Modelos (deben ser los mismos que en grpc_server.py) ---
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
    description = db.Column(db.Text, nullable=True) # Columna de descripción
    price = db.Column(db.Numeric(10, 2), nullable=False) # Columna de precio base
    imagen_base64 = db.Column(db.Text, nullable=True) # Columna para imagen en Base64
    sucursales_info = db.relationship('ProductoSucursal', backref='producto', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'marca': self.marca,
            'description': self.description,
            'price': float(self.price),
            'imagen_base64': self.imagen_base64
        }

class ProductoSucursal(db.Model):
    __tablename__ = 'productos_sucursales'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursales.id'), nullable=False)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('producto_id', 'sucursal_id', name='_producto_sucursal_uc'),)
    def to_dict(self):
        return {'id': self.id, 'producto_id': self.producto_id, 'sucursal_id': self.sucursal_id, 'precio': float(ps.precio), 'stock': self.stock}

# --- NUEVOS MODELOS PARA TRANSBANK ---
class Orden(db.Model):
    __tablename__ = 'ordenes'
    id = db.Column(db.Integer, primary_key=True)
    buy_order = db.Column(db.String(50), unique=True, nullable=False, index=True) # ID único de Transbank
    session_id = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PENDING') # PENDING, PAID, REJECTED, CANCELLED
    transaction_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    authorization_code = db.Column(db.String(20), nullable=True)
    card_number = db.Column(db.String(4), nullable=True) # Últimos 4 dígitos de la tarjeta
    response_code = db.Column(db.Integer, nullable=True) # Código de respuesta de Transbank
    
    # Relación con los items de la orden
    items = db.relationship('OrderItem', backref='orden', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'buy_order': self.buy_order,
            'session_id': self.session_id,
            'amount': float(self.amount),
            'status': self.status,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'authorization_code': self.authorization_code,
            'card_number': self.card_number,
            'response_code': self.response_code
        }
        
class OrderItem(db.Model):
    __tablename__ = 'orden_items'
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursales.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Numeric(10, 2), nullable=False) # Precio unitario al momento de la compra

    # Relaciones de vuelta para acceder fácilmente a los objetos de producto y sucursal
    producto = db.relationship('Producto')
    sucursal = db.relationship('Sucursal')

    def to_dict(self):
        return {
            'id': self.id,
            'orden_id': self.orden_id,
            'producto_id': self.producto_id,
            'sucursal_id': self.sucursal_id,
            'quantity': self.quantity,
            'price_at_purchase': float(self.price_at_purchase)
        }
        
        
# --- Implementación de Server-Sent Events (SSE) ---
clients = []
low_stock_threshold = 10 # Umbral de stock bajo para alertas SSE

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

# --- Definición de Rutas Flask ---
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
        # CORREGIDO: Usar Producto.query.filter en lugar de db.query.filter
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
            # CORREGIDO: Usar db.session.get() en lugar de .query.get()
            sucursal = db.session.get(Sucursal, ps.sucursal_id)
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

# --- Ruta para Añadir Productos (Cliente gRPC en Flask) ---
@app.route('/api/products/add', methods=['POST'])
def add_product_via_grpc():
    data = request.json
    name = data.get('name')
    description = data.get('description')
    price = data.get('price')
    image_base64 = data.get('image')

    if not all([name, price is not None]):
        return jsonify({"error": "Nombre y Precio son campos obligatorios."}), 400

    try:
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = product_pb2_grpc.ProductServiceStub(channel)
            print(f"DEBUG (Flask Client): Calling gRPC AddProduct with: Name={name}, Price={price}")
            grpc_request = product_pb2.AddProductRequest(
                name=name,
                description=description,
                price=float(price),
                image_base64=image_base64 if image_base64 else ""
            )
            grpc_response = stub.AddProduct(grpc_request)
            print(f"DEBUG (Flask Client): gRPC response: {grpc_response.message}")

            if grpc_response.success:
                return jsonify({
                    "message": grpc_response.message,
                    "product_id": grpc_response.product_id
                }), 201
            else:
                if "ya existe" in grpc_response.message:
                    return jsonify({"error": grpc_response.message}), 409
                return jsonify({"error": grpc_response.message}), 500
    except grpc.RpcError as e:
        print(f"ERROR (Flask Client): Fallo al llamar al servicio gRPC: {e}")
        return jsonify({"error": f"Fallo al comunicar con el servicio de productos: {e.details}"}), 500
    except Exception as e:
        print(f"ERROR (Flask Client): Error inesperado al añadir producto: {e}")
        return jsonify({"error": f"Ocurrió un error inesperado al añadir producto: {str(e)}"}), 500

@app.route('/api/exchange_rate', methods=['GET'])
def get_exchange_rate():
    try:
        print(f"DEBUG (Flask App): Requesting exchange rate from: {EXCHANGE_RATE_API_BASE_URL}")
        response = requests.get(EXCHANGE_RATE_API_BASE_URL)
        response.raise_for_status()
        data = response.json()
        print(f"DEBUG (Flask App): Full API response for exchange rate: {json.dumps(data, indent=2)}")

        if data.get('result') == 'error':
            error_type = data.get('error-type', 'unknown_error')
            print(f"ERROR (Flask App): ExchangeRate-API returned an error: {error_type}")
            return jsonify({"message": f"API de tipo de cambio devolvió un error: {error_type}", "error": error_type}), 500

        exchange_rate_usd = data['conversion_rates']['USD']
        rate_usd_to_clp = 1 / exchange_rate_usd

        print(f"DEBUG (Flask App): Tasa de cambio obtenida (1 USD = {rate_usd_to_clp:.2f} CLP)")
        return jsonify({"rate": round(rate_usd_to_clp, 2)}), 200
    except requests.exceptions.RequestException as e:
        print(f"ERROR (Flask App): Error al conectar con la API de tipo de cambio: {e}")
        return jsonify({"message": "Error al conectar con el servicio de tipo de cambio", "error": str(e)}), 500
    except KeyError as e:
        print(f"ERROR (Flask App): Error al parsear la respuesta de la API (clave no encontrada): {e}. Respuesta completa: {json.dumps(data, indent=2) if 'data' in locals() else 'No data received'}")
        return jsonify({"message": "Error al procesar la respuesta del tipo de cambio (estructura inesperada)", "error": f"Clave no encontrada: {e}"}), 500
    except Exception as e:
        print(f"ERROR (Flask App): Error inesperado al obtener el tipo de cambio: {e}")
        return jsonify({"message": "Error interno al obtener el tipo de cambio", "error": str(e)}), 500
    
# --- RUTA PARA INICIAR PAGO CON TRANSBANK ---
@app.route('/api/webpay/create', methods=['POST'])
def create_webpay_transaction():
    data = request.json
    buy_order = data.get('buy_order')
    session_id = data.get('session_id')
    amount = data.get('amount')
    cart_items = data.get('cart_items')

    # Determinar la URL de retorno, importante para despliegues en Render u otros PaaS
    if os.environ.get('ON_RENDER'):
        return_url_base = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"
    else:
        return_url_base = "http://127.0.0.1:5000"

    return_url = f"{return_url_base}/api/webpay/commit"

    if not all([buy_order, session_id, amount, cart_items]):
        return jsonify({"message": "Missing required data for Transbank transaction (buy_order, session_id, amount, cart_items)"}), 400

    try:
        amount = int(amount)

        # --- ALMACENAR ORDEN EN LA BASE DE DATOS COMO PENDIENTE ---
        new_order = Orden(
            buy_order=buy_order,
            session_id=session_id,
            amount=amount,
            status='PENDING' # Estado inicial de la orden
        )
        db.session.add(new_order)
        db.session.flush() # Esto asigna un ID a new_order sin hacer un commit aún

        for item_data in cart_items:
            order_item = OrderItem(
                orden_id=new_order.id,
                producto_id=item_data['product_id'],
                sucursal_id=item_data['sucursal_id'],
                quantity=item_data['quantity'],
                price_at_purchase=item_data['price']
            )
            db.session.add(order_item)
        
        db.session.commit() # Ahora sí, commit para guardar la orden y sus items
        print(f"DEBUG: Orden {buy_order} y sus items guardados en DB como PENDING.")
        # -----------------------------------------------------------

        response = webpay_transaction.create(buy_order, session_id, amount, return_url)

        print(f"DEBUG: Tipo de respuesta de Transbank create(): {type(response)}")
        print(f"DEBUG: Contenido de respuesta de Transbank create(): {response.__dict__ if hasattr(response, '__dict__') else response}")

        # Asegurarse de que el retorno sea siempre un JSON con url y token, o un error JSON
        if hasattr(response, 'url') and hasattr(response, 'token'):
            return jsonify({
                "url": response.url,
                "token": response.token
            })
        elif isinstance(response, dict) and 'url' in response and 'token' in response:
            print("DEBUG: Transbank create() devolvió un diccionario con url y token. Procesando como éxito.")
            return jsonify({
                "url": response['url'],
                "token": response['token']
            })
        else:
            # Si la respuesta no tiene el formato esperado, capturar cualquier mensaje de error.
            # Esto evita que se envíe "1" si la librería no maneja todos los casos como objetos.
            error_message = "Respuesta inesperada de Transbank al crear transacción."
            if isinstance(response, dict) and 'error_message' in response:
                error_message = response.get('error_message')
            elif isinstance(response, dict) and 'error' in response:
                error_message = str(response.get('error'))
            elif isinstance(response, str): # Si la respuesta es una cadena como "1"
                 error_message = f"Transbank devolvió una respuesta inesperada: {response}. Esperado URL y Token."
            else:
                 error_message = f"Transbank devolvió un tipo de objeto inesperado: {type(response)}. Detalles: {str(response)}"


            print(f"ERROR: Transbank create() no devolvió objeto esperado o dict con url/token: {response}")
            # Si falla la creación de Transbank, marca la orden como CANCELLED o REJECTED
            new_order.status = 'CANCELLED' # O 'CREATE_FAILED'
            db.session.commit()
            return jsonify({"error": error_message, "transbank_raw_response": str(response)}), 500

    except Exception as e:
        db.session.rollback() # Si algo falla antes del commit, revierte
        print(f"Error EXCEPCIÓN al crear transacción Transbank: {e}")
        return jsonify({"error": str(e)}), 500

# --- RUTA PARA CONFIRMAR PAGO CON TRANSBANK (POST-REDIRECCIÓN) ---
@app.route('/api/webpay/commit', methods=['GET', 'POST'])
def commit_webpay_transaction():
    token_ws = None
    if request.method == 'POST':
        token_ws = request.form.get('token_ws')
    elif request.method == 'GET':
        token_ws = request.args.get('token_ws')

    if not token_ws:
        print("ERROR: Token de transacción no encontrado en la respuesta de Transbank.")
        return render_template('payment_failure.html', message="Token de transacción no encontrado."), 400

    current_order = None # Inicializamos para usarlo en el bloque finally si es necesario

    try:
        response = webpay_transaction.commit(token_ws)

        print(f"DEBUG: Tipo de respuesta de Transbank commit(): {type(response)}")
        print(f"DEBUG: Contenido de respuesta de Transbank commit(): {response.__dict__ if hasattr(response, '__dict__') else response}")

        # Extraer el buy_order del response para buscar la orden pendiente
        # Usamos .get() de forma segura, ya que response puede ser un dict
        buy_order_from_tbk = getattr(response, 'buy_order', response.get('buy_order', None))

        # --- RECUPERAR ORDEN PENDIENTE DE LA BASE DE DATOS ---
        if buy_order_from_tbk:
            current_order = db.session.query(Orden).filter_by(buy_order=buy_order_from_tbk, status='PENDING').first()
            if not current_order:
                print(f"ERROR: Orden pendiente con buy_order {buy_order_from_tbk} no encontrada o ya procesada.")
                # Si la orden no se encuentra, podría ser un reintento o un problema
                return render_template('payment_failure.html', message="Error: Orden no encontrada o ya procesada."), 404
        else:
            print("ERROR: Buy Order no encontrado en la respuesta de Transbank.")
            return render_template('payment_failure.html', message="Error: Buy Order no recibido de Transbank."), 400
        # -----------------------------------------------------

        # Si la respuesta es un diccionario con 'error_message'
        if isinstance(response, dict) and 'error_message' in response:
            error_message_from_tbk = response.get('error_message', 'Error desconocido en Transbank.')
            print(f"ERROR: Transbank commit() devolvió un error: {error_message_from_tbk}")
            current_order.status = 'REJECTED' # Marca la orden como rechazada
            db.session.commit()
            return render_template('payment_failure.html', message=f"Error en Transbank: {error_message_from_tbk}"), 500

        # Acceder a las propiedades de la respuesta de forma segura
        response_code = getattr(response, 'response_code', response.get('response_code', None))
        status_tbk = getattr(response, 'status', response.get('status', 'UNKNOWN'))
        authorization_code = getattr(response, 'authorization_code', response.get('authorization_code', 'N/A'))
        
        # Parsear transaction_date si es necesario
        transaction_date_str = getattr(response, 'transaction_date', response.get('transaction_date', 'N/A'))
        transaction_date = None
        if transaction_date_str and transaction_date_str != 'N/A':
            try:
                # Intenta parsear la fecha. El formato puede variar.
                # Un formato común de Transbank es "AAAA-MM-DDTHH:MM:SS.sssZ"
                transaction_date = datetime.fromisoformat(transaction_date_str.replace('Z', '+00:00'))
            except ValueError:
                print(f"WARNING: No se pudo parsear transaction_date: {transaction_date_str}")
                transaction_date = None
        
        card_detail = getattr(response, 'card_detail', response.get('card_detail', {}))
        card_number = getattr(card_detail, 'card_number', card_detail.get('card_number', 'N/A'))
        
        if response_code == 0:
            print(f"DEBUG: ¡Transacción Webpay exitosa! Order ID: {buy_order_from_tbk}, Monto: {current_order.amount}")
            
            # --- Lógica de Descuento de Stock ---
            # Usa los items de la orden recuperada de la DB
            for item in current_order.items:
                product_id = item.producto_id
                sucursal_id = item.sucursal_id
                quantity = item.quantity

                try:
                    # CORREGIDO: Usar db.session.get() para ProductoSucursal si tienes el ID de la tabla
                    # O usa filter_by() como ya está para evitar la advertencia si no es PK
                    ps = ProductoSucursal.query.filter_by(
                        producto_id=product_id,
                        sucursal_id=sucursal_id
                    ).with_for_update().first() # with_for_update() para asegurar atomicidad si hay concurrencia

                    if ps:
                        if ps.stock >= quantity:
                            ps.stock -= quantity
                            db.session.add(ps)
                            print(f"DEBUG: Descontado {quantity} unidades de Producto {product_id} en Sucursal {sucursal_id}. Nuevo stock: {ps.stock}")
                            
                            # Notificar sobre stock bajo si aplica (usando el umbral global)
                            if ps.stock <= low_stock_threshold: # Usando el umbral global
                                # CORREGIDO: Usar db.session.get() para Producto y Sucursal para notificación
                                producto_notif = db.session.get(Producto, ps.producto_id)
                                sucursal_notif = db.session.get(Sucursal, ps.sucursal_id)

                                notify_clients({
                                    'product_id': ps.producto_id,
                                    'product_name': producto_notif.nombre if producto_notif else 'N/A',
                                    'sucursal_id': ps.sucursal_id,
                                    'sucursal_name': sucursal_notif.nombre if sucursal_notif else 'N/A',
                                    'current_stock': ps.stock
                                }, event='low_stock_alert') # Asegúrate de que el evento es 'low_stock_alert' para el frontend
                        else:
                            print(f"ADVERTENCIA: Stock insuficiente para Producto {product_id} en Sucursal {sucursal_id}. Disponible: {ps.stock}, Solicitado: {quantity}")
                            # Si el stock es insuficiente, Transbank ya aprobó el pago.
                            # Aquí se podría implementar una lógica de reembolso o pedido a proveedor.
                            # Por ahora, solo logueamos la advertencia.
                    else:
                        print(f"ADVERTENCIA: ProductoSucursal no encontrado para Producto {product_id} en Sucursal {sucursal_id}. No se descontó stock.")
                except Exception as stock_e:
                    print(f"ERROR: Fallo al descontar stock para item de orden {item.id}: {stock_e}")
            
            # Actualiza el estado de la orden en la DB a PAGADO/COMPLETADO
            current_order.status = 'PAID'
            current_order.authorization_code = authorization_code
            current_order.card_number = card_number
            current_order.response_code = response_code
            current_order.transaction_date = transaction_date # Se asigna el objeto datetime o None
            db.session.add(current_order) # Agrega la orden modificada a la sesión

            db.session.commit() # Confirma todos los cambios de stock y el estado de la orden
            print(f"DEBUG: Orden {current_order.buy_order} marcada como PAID y stock descontado.")


            return render_template('payment_success.html',
                                   message=f"¡Pago exitoso! ID de Autorización: {authorization_code}",
                                   buy_order=buy_order_from_tbk, # Usar el buy_order real de la orden
                                   amount=current_order.amount, # Usar el monto de la orden guardada
                                   card_number=card_number,
                                   transaction_date=transaction_date_str, # Mostrar la cadena original en el HTML
                                   status=status_tbk)
        else:
            # La transacción no fue exitosa (ej. tarjeta rechazada)
            error_message = f"Pago fallido. Código de respuesta: {response_code}. "
            if response_code == -1:
                error_message += "La tarjeta no posee fondos suficientes."
            elif response_code == -2:
                error_message += "Tarjeta o clave inválida."
            elif response_code == -3:
                error_message += "Error de Transacción (ej. excedió monto máximo diario)."
            elif response_code == -4:
                error_message += "Transacción Rechazada por Transbank."
            elif response_code == -5:
                error_message += "Error de la operación."
            elif response_code == -6:
                error_message += "Excedió número de reintentos de clave."
            elif response_code == -7:
                error_message += "Rechazada - No se puede realizar la venta."
            else:
                error_message += "Mensaje detallado no disponible o código desconocido."

            print(f"ERROR: Transacción fallida. Respuesta completa: {response}")
            
            # Marca la orden como REJECTED
            current_order.status = 'REJECTED'
            current_order.authorization_code = authorization_code
            current_order.card_number = card_number
            current_order.response_code = response_code
            current_order.transaction_date = transaction_date
            db.session.commit()
            print(f"DEBUG: Orden {current_order.buy_order} marcada como REJECTED.")

            return render_template('payment_failure.html',
                                   message=error_message,
                                   buy_order=buy_order_from_tbk,
                                   amount=current_order.amount,
                                   status=status_tbk,
                                   response_code=response_code), 400

    except Exception as e:
        db.session.rollback() # En caso de cualquier excepción, revierte la transacción de la DB
        print(f"Error EXCEPCIÓN al confirmar transacción Transbank: {e}")
        # Si la orden ya se había creado y se encuentra en la excepción, márcala como 'FAILED'
        if current_order and current_order.id and current_order.status == 'PENDING':
             current_order.status = 'FAILED'
             db.session.commit()
             print(f"DEBUG: Orden {current_order.buy_order} marcada como FAILED tras excepción.")
        return render_template('payment_failure.html', message=f"Error interno al confirmar el pago: {e}"), 500 
    
@app.route('/events/low-stock')
def low_stock_events():
    client_queue = queue.Queue()
    clients.append(client_queue)
    print("DEBUG (Flask App): New SSE client connected.")
    @stream_with_context
    def event_stream():
        while True:
            try:
                message = client_queue.get(timeout=1.0)
                yield message
            except queue.Empty:
                yield ': keepalive\n\n'
            except Exception as e:
                print(f"ERROR (Flask App): Error in SSE stream for a client: {e}")
                break
        if client_queue in clients:
            clients.remove(client_queue)
            print("DEBUG (Flask App): SSE client disconnected.")
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    with app.app_context():
        print("DEBUG (Flask App): Attempting to create database tables...")
        try:
            db.drop_all()
            db.create_all()
            print("DEBUG (Flask App): Database tables (re)created successfully.")

            if not Sucursal.query.first():
                print("DEBUG (Flask App): Adding sample sucursal data...")
                sucursal1 = Sucursal(nombre='Sucursal Centro', direccion='Calle Falsa 123')
                sucursal2 = Sucursal(nombre='Casa Matriz', direccion='Avenida Siempre Viva 742')
                db.session.add_all([sucursal1, sucursal2])
                db.session.commit()
                print("DEBUG (Flask App): Sample sucursales added.")

            if not Producto.query.first():
                print("DEBUG (Flask App): Adding sample product data...")
                producto1 = Producto(nombre='Martillo', marca='ToolCo', description='Martillo de orejas para trabajos generales.', price=8500.00, imagen_base64='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')
                producto2 = Producto(nombre='Destornillador Phillips', marca='FixIt', description='Destornillador Phillips de punta magnética.', price=3200.00, imagen_base64='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')
                producto3 = Producto(nombre='Sierra', marca='CutMaster', description='Sierra de mano para cortar madera y plástico.', price=15000.00, imagen_base64='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')
                db.session.add_all([producto1, producto2, producto3])
                db.session.commit()
                print("DEBUG (Flask App): Sample productos added.")

                # CORREGIDO: Usar db.session.get() para obtener instancias por ID
                s1 = db.session.get(Sucursal, 1) 
                s2 = db.session.get(Sucursal, 2)
                p1 = db.session.get(Producto, 1)
                p2 = db.session.get(Producto, 2)
                p3 = db.session.get(Producto, 3)

                if s1 and s2 and p1 and p2 and p3:
                    ps1 = ProductoSucursal(producto=p1, sucursal=s1, precio=9000.00, stock=15)
                    ps2 = ProductoSucursal(producto=p1, sucursal=s2, precio=8500.00, stock=50)
                    ps3 = ProductoSucursal(producto=p2, sucursal=s1, precio=3500.00, stock=30)
                    ps4 = ProductoSucursal(producto=p3, sucursal=s2, precio=16000.00, stock=25)

                    db.session.add_all([ps1, ps2, ps3, ps4])
                    db.session.commit()
                    print("DEBUG (Flask App): Sample ProductoSucursal data added.")
                else:
                    print("WARNING (Flask App): Could not add ProductoSucursal data, some parent records not found.")

        except SQLAlchemyError as e:
            print(f"ERROR (Flask App): SQLAlchemy error during initialization: {e}")
        except Exception as e:
            print(f"ERROR (Flask App): An unexpected error occurred during initialization: {e}")

    print("DEBUG (Flask App): Attempting to run Flask app...")
    app.run(debug=True, port=5000, threaded=True, use_reloader=False)

