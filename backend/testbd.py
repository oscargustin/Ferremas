import psycopg2
import os

    # Configuración de la base de datos (debe coincidir con la de tu app.py)
    # Intenta obtener de la variable de entorno, si no, usa el valor por defecto
    # ASEGÚRATE DE QUE ESTA URL COINCIDA EXACTAMENTE CON LA DE TU app.py
    # Si estás usando un archivo .env, asegúrate de que DATABASE_URL esté definida allí.
db_url = os.environ.get('DATABASE_URL', 'postgresql://ferremas_user:password123@localhost:5432/ferremasbd')

    # Para cargar variables de entorno desde un archivo .env si lo estás usando
try:
        from dotenv import load_dotenv
        load_dotenv()
        db_url = os.environ.get('DATABASE_URL', 'postgresql://ferremas_user:password123@localhost:5432/ferremasbd')
except ImportError:
        # Si python-dotenv no está instalado, simplemente usa la URL por defecto
        pass


    # Parsear la URL de la base de datos
try:
        parts = db_url.split('://')[1].split('@')
        user_pass = parts[0].split(':')
        host_port_db = parts[1].split('/')

        user = user_pass[0]
        password = user_pass[1]
        host_port = host_port_db[0].split(':')
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else '5432'
        dbname = host_port_db[1]

        conn_params = {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }

        print(f"Intentando conectar con: dbname='{dbname}', user='{user}', host='{host}', port='{port}'")

        # Intentar conectar
        connection = psycopg2.connect(**conn_params)
        print("¡Conexión a la base de datos exitosa!")
        connection.close()
except Exception as e:
        print(f"¡Error al conectar a la base de datos!: {e}")
        print("\n--- Posibles causas del error de conexión ---")
        print("1. El servidor PostgreSQL no está corriendo en 'localhost:5432'.")
        print("2. Las credenciales (usuario/contraseña) son incorrectas para el usuario 'ferremas_user'.")
        print("3. El nombre de la base de datos 'ferremasbdyy' es incorrecto o no existe.")
        print("4. Hay un firewall bloqueando la conexión al puerto 5432.")
        print("5. Si usas un archivo .env, no se está cargando correctamente o la variable DATABASE_URL está mal definida.")
        print("---------------------------------------------")

    