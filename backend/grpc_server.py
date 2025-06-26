# Archivo: backend/grpc_server.py
import os
import time
from concurrent import futures

# Importar y cargar dotenv al principio de este script
from dotenv import load_dotenv
load_dotenv() # Carga las variables de entorno desde .env

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

# --- Importaciones gRPC ---
import grpc
import product_pb2
import product_pb2_grpc

# --- Configuración de la Base de Datos PostgreSQL (Mismo que en app.py) ---
grpc_app = Flask(__name__)
# Lee DATABASE_URL desde el .env; si no existe, usa el valor por defecto
grpc_app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://ferremas_user:password123@localhost:5432/ferremasbd')
grpc_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

grpc_db = SQLAlchemy(grpc_app)

print(f"DEBUG (gRPC Server): SQLAlchemy DB URI for gRPC: {grpc_app.config['SQLALCHEMY_DATABASE_URI']}")

# --- Definición de Modelos (deben ser los mismos que en app.py) ---
class Sucursal(grpc_db.Model):
    __tablename__ = 'sucursales'
    id = grpc_db.Column(grpc_db.Integer, primary_key=True)
    nombre = grpc_db.Column(grpc_db.String(100), nullable=False)
    direccion = grpc_db.Column(grpc_db.String(200), nullable=True)
    productos_sucursales = grpc_db.relationship('ProductoSucursal', backref='sucursal', lazy=True)

class Producto(grpc_db.Model):
    __tablename__ = 'productos'
    id = grpc_db.Column(grpc_db.Integer, primary_key=True)
    nombre = grpc_db.Column(grpc_db.String(100), nullable=False)
    marca = grpc_db.Column(grpc_db.String(100), nullable=True)
    description = grpc_db.Column(grpc_db.Text, nullable=True)
    price = grpc_db.Column(grpc_db.Numeric(10, 2), nullable=False)
    imagen_base64 = grpc_db.Column(grpc_db.Text, nullable=True)
    sucursales_info = grpc_db.relationship('ProductoSucursal', backref='producto', lazy=True)

class ProductoSucursal(grpc_db.Model):
    __tablename__ = 'productos_sucursales'
    id = grpc_db.Column(grpc_db.Integer, primary_key=True)
    producto_id = grpc_db.Column(grpc_db.Integer, grpc_db.ForeignKey('productos.id'), nullable=False)
    sucursal_id = grpc_db.Column(grpc_db.Integer, grpc_db.ForeignKey('sucursales.id'), nullable=False)
    precio = grpc_db.Column(grpc_db.Numeric(10, 2), nullable=False)
    stock = grpc_db.Column(grpc_db.Integer, nullable=False)
    __table_args__ = (grpc_db.UniqueConstraint('producto_id', 'sucursal_id', name='_producto_sucursal_uc'),)


# --- Implementación del Servicio gRPC ---
class ProductServiceServicer(product_pb2_grpc.ProductServiceServicer):
    def AddProduct(self, request, context):
        with grpc_app.app_context(): # Usamos grpc_app para el contexto aquí
            print(f"DEBUG (gRPC Servicer): Received AddProduct request: Name={request.name}, Price={request.price}")
            try:
                existing_product = Producto.query.filter_by(nombre=request.name).first()

                if existing_product:
                    print(f"DEBUG (gRPC Servicer): Product '{request.name}' already exists.")
                    context.set_code(grpc.StatusCode.ALREADY_EXISTS)
                    context.set_details(f"El producto '{request.name}' ya existe.")
                    return product_pb2.AddProductResponse(success=False, message=f"El producto '{request.name}' ya existe. No se añadió.")

                new_product = Producto(
                    nombre=request.name,
                    marca="Generica",
                    description=request.description if request.description else None,
                    price=request.price,
                    imagen_base64=request.image_base64 if request.image_base64 else None
                )
                grpc_db.session.add(new_product)
                grpc_db.session.commit()

                print(f"DEBUG (gRPC Servicer): Product '{new_product.nombre}' added with ID: {new_product.id}")
                return product_pb2.AddProductResponse(
                    success=True,
                    message=f"Producto '{new_product.nombre}' añadido con éxito.",
                    product_id=new_product.id
                )
            except SQLAlchemyError as e:
                grpc_db.session.rollback()
                print(f"ERROR (gRPC Servicer): Database error adding product: {e}")
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Error de base de datos al añadir producto: {str(e)}")
                return product_pb2.AddProductResponse(success=False, message="Error de base de datos al añadir producto.")
            except Exception as e:
                grpc_db.session.rollback()
                print(f"ERROR (gRPC Servicer): Unexpected error adding product: {e}")
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Error interno al añadir producto: {str(e)}")
                return product_pb2.AddProductResponse(success=False, message="Error interno al añadir producto.")

def serve():
    import socket
    port_to_check = 50051
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port_to_check))
            print(f"DEBUG (gRPC Server Init): Puerto {port_to_check} está disponible para binding.")
        except socket.error as e:
            print(f"ERROR (gRPC Server Init): Puerto {port_to_check} NO DISPONIBLE: {e}")
            print("ERROR (gRPC Server Init): Intenta detener cualquier proceso que esté usando este puerto.")
            return

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    product_pb2_grpc.add_ProductServiceServicer_to_server(ProductServiceServicer(), server)
    
    server.add_insecure_port(f'0.0.0.0:{port_to_check}') 
    
    print(f"DEBUG (gRPC Server): Servidor gRPC iniciado en el puerto {port_to_check}.")
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        print("DEBUG (gRPC Server): Servidor gRPC detenido por KeyboardInterrupt.")
        server.stop(0)
    except Exception as e:
        print(f"ERROR (gRPC Server): Error inesperado en el hilo del servidor gRPC: {e}")
        server.stop(0)

if __name__ == '__main__':
    serve()
