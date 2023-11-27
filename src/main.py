import socket
import random
import threading

# Server ayarları
HOST = '127.0.0.1'
PORT = 5555

# Bağlı kullanıcıları tutacak dictionary
connected_clients = {}

lock = threading.Lock()
number_of_clients = 0

def generate_unique_id():
    while True:
        new_id = random.randint(100, 999999)
        with lock:
            # Yeni ID dictionary'de var mı kontrol et, yoksa atamayı yap
            if new_id not in connected_clients:
                return new_id

def handle_client(client_socket, client_address):
    # Unique ID oluştur
    global number_of_clients
    unique_id = generate_unique_id()
    number_of_clients += 1

    with lock:
        # Client'a ID'yi gönder
        client_socket.send(str(unique_id).encode())

        # Dictionary'e ekle
        connected_clients[unique_id] = {'ip': client_address, 'state': 'connected'}

    print(f"New connection from {client_address}. Assigned ID: {unique_id}. Number of clients is {number_of_clients}")

    # YİĞİDO AŞAĞISI ÇALIŞMIYOR ASLA. Whilede bişiler yazmadım daha. Belki bunla alakalıdır
    # ama ctrl+c ile çıkınca clienttan bu finallye falanda girmiyor. Bu yüzden client sayısı da azalmıyor.
    # server ctrl+c ile kapanmıyor client bağlansada bağlanmasada anlamadım
    '''try:
        while True:
            # Burada bağlı kalındığı sürece işlemleri gerçekleştirebilirsiniz
            pass
    except KeyboardInterrupt:
        print(f"Connection with ID {unique_id} closed.")
    finally:
        # Bağlantı sona erdiğinde dictionary'den kaldır ve Client sayısını bir azalt.
        with lock:
            number_of_clients -= 1
            del connected_clients[unique_id]'''

if __name__ == "__main__":
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()

    print(f"Server listening on {HOST}:{PORT}")

    while True:
        client_socket, client_address = server_socket.accept()
        client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        client_thread.start()
