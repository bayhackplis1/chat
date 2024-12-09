import socket
import threading
import random
import json
from cryptography.fernet import Fernet

# Generar una clave para el cifrado
key = Fernet.generate_key()
cipher = Fernet(key)

# Solicitar nombre de usuario
username = input("Ingrese su nombre de usuario: ").strip()
if not username:
    username = f"Usuario{random.randint(1000, 9999)}"

# Variables de conexión
HOST = '127.0.0.1'
PORT = random.randint(49152, 65535)  # Puerto aleatorio para conexión TCP
BROADCAST_PORT = 54545  # Puerto fijo para difusión UDP
users_online = {}  # Diccionario de usuarios en línea {nombre: (IP, puerto)}
connection_requests = []  # Solicitudes de conexión pendientes

# Bloqueo para sincronización
lock = threading.Lock()

# Estadísticas
message_stats = {"sent": 0, "received": 0}


# Función para manejar mensajes recibidos
def handle_client(conn, addr):
    try:
        data = conn.recv(1024).decode()
        if data.startswith("[REQUEST]"):
            peer_name = data.split(":")[1].strip()
            with lock:
                connection_requests.append((peer_name, addr[0]))
            print(f"\n[INFO] Nueva solicitud de conexión de {peer_name}. Revisa 'Ver solicitudes de conexión'.")
        elif data.startswith("[MESSAGE]"):
            decrypted_message = cipher.decrypt(data[9:].encode()).decode()
            print(f"\n[CHAT] {decrypted_message}")
        else:
            print(f"[ERROR] Mensaje desconocido recibido de {addr[0]}")
    except Exception as e:
        print(f"[ERROR] Error manejando cliente: {e}")
    finally:
        conn.close()


# Función para iniciar el servidor
def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((HOST, PORT))
        server.listen(5)
        print(f"\n[INFO] Servidor iniciado en {HOST}:{PORT}, esperando conexiones...")
        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()
    except Exception as e:
        print(f"[ERROR] Error iniciando el servidor: {e}")
    finally:
        server.close()


# Función para manejar difusión UDP
def broadcast_listener():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(("", BROADCAST_PORT))
    while True:
        try:
            data, addr = udp_socket.recvfrom(1024)
            user_info = json.loads(data.decode())
            with lock:
                users_online[user_info['username']] = (addr[0], user_info['port'])
        except Exception as e:
            print(f"[ERROR] Error en difusión UDP: {e}")


# Función para anunciarse por difusión UDP
def broadcast_announce():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        try:
            message = json.dumps({"username": username, "port": PORT})
            udp_socket.sendto(message.encode(), ('<broadcast>', BROADCAST_PORT))
        except Exception as e:
            print(f"[ERROR] Error enviando difusión UDP: {e}")
        finally:
            threading.Event().wait(5)  # Enviar cada 5 segundos


# Función para listar usuarios en línea
def list_users():
    print("\n[USUARIOS EN LÍNEA]")
    with lock:
        if not users_online:
            print("[INFO] No hay usuarios en línea.")
        else:
            for idx, (user, (ip, port)) in enumerate(users_online.items(), start=1):
                print(f"{idx}. {user} - {ip}:{port}")
    print("-" * 40)


# Función para solicitar conexión a un usuario
def request_connection():
    list_users()
    try:
        user_index = int(input("\n[INPUT] Seleccione el número del usuario para conectarse: ")) - 1
        selected_user = list(users_online.keys())[user_index]
        ip, port = users_online[selected_user]
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((ip, port))
        conn.send(f"[REQUEST]:{username}".encode())
        print(f"[INFO] Solicitud de conexión enviada a {selected_user}. Esperando respuesta.")
        conn.close()
    except (IndexError, ValueError):
        print("[ERROR] Selección inválida.")
    except Exception as e:
        print(f"[ERROR] Error al solicitar conexión: {e}")


# Función para revisar y aceptar/rechazar solicitudes de conexión
def handle_requests():
    global connection_requests
    with lock:
        if not connection_requests:
            print("\n[INFO] No tienes solicitudes pendientes.")
            return
        for idx, (user, ip) in enumerate(connection_requests, start=1):
            print(f"{idx}. Solicitud de {user} desde {ip}")
    try:
        choice = int(input("\n[INPUT] Seleccione una solicitud para gestionar o 0 para volver: "))
        if choice == 0:
            return
        selected_request = connection_requests.pop(choice - 1)
        user, ip = selected_request
        decision = input(f"[INPUT] ¿Aceptar la conexión de {user}? (s/n): ").strip().lower()
        if decision == "s":
            print(f"[INFO] Conexión aceptada con {user}.")
            threading.Thread(target=chat_session, args=(ip, users_online[user][1], user)).start()
        else:
            print(f"[INFO] Conexión rechazada con {user}.")
    except (IndexError, ValueError):
        print("[ERROR] Selección inválida.")
    except Exception as e:
        print(f"[ERROR] Error gestionando solicitud: {e}")


# Función para gestionar una sesión de chat
def chat_session(ip, port, peer_name):
    try:
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((ip, port))
        while True:
            print("\n1. Enviar mensaje")
            print("2. Enviar mensaje de alarma")
            print("3. Enviar mensaje de emergencia")
            print("4. Salir del chat")
            choice = input("\n[INPUT] Selecciona una opción: ").strip()
            if choice == "1":
                message = input(f"[{peer_name}]> Escribe tu mensaje: ")
                encrypted_message = cipher.encrypt(message.encode())
                conn.sendall(f"[MESSAGE]{encrypted_message.decode()}".encode())
                message_stats["sent"] += 1
            elif choice == "2":
                alarm_message = "[ALARMA] ¡Algo no está bien!"
                encrypted_message = cipher.encrypt(alarm_message.encode())
                conn.sendall(f"[MESSAGE]{encrypted_message.decode()}".encode())
                message_stats["sent"] += 1
            elif choice == "3":
                emergency_message = "[EMERGENCIA] ¡Necesito ayuda inmediata!"
                encrypted_message = cipher.encrypt(emergency_message.encode())
                conn.sendall(f"[MESSAGE]{encrypted_message.decode()}".encode())
                message_stats["sent"] += 1
            elif choice == "4":
                conn.close()
                print(f"\n[INFO] Chat con {peer_name} finalizado.")
                break
            else:
                print("[ERROR] Opción no válida.")
    except Exception as e:
        print(f"[ERROR] Error en la sesión de chat con {peer_name}: {e}")


# Menú principal
def main():
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=broadcast_listener, daemon=True).start()
    threading.Thread(target=broadcast_announce, daemon=True).start()

    while True:
        try:
            print("\n" + "-" * 40)
            print("[MENÚ PRINCIPAL]")
            print("1. Ver usuarios en línea")
            print("2. Solicitar conexión")
            print("3. Ver solicitudes de conexión")
            print("4. Salir")
            print("-" * 40)

            choice = input("[INPUT] Elige una opción: ").strip()
            if choice == "1":
                list_users()
            elif choice == "2":
                request_connection()
            elif choice == "3":
                handle_requests()
            elif choice == "4":
                print("\n[INFO] Saliendo del programa. ¡Hasta luego!")
                break
            else:
                print("[ERROR] Opción no válida.")
        except KeyboardInterrupt:
            print("\n[INFO] Programa detenido por el usuario.")
            break
        except Exception as e:
            print(f"[ERROR] Error en el menú principal: {e}")


if __name__ == "__main__":
    main()
