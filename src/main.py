import socket
import random
import threading
import time
import signal
import os
import sys


HOST = '127.0.0.1'
PORT = 5555

clients = {}

lock: threading.Lock = threading.Lock()
numberOfClients = 0


def generateUniqueId() -> int:
    while True:
        newId = random.randint(100, 999999)
        if newId not in clients:
            return newId


def handleClient(clientSocket: socket.socket, clientAddress: tuple) -> None:
    global numberOfClients
    uniqueId = generateUniqueId()
    numberOfClients += 1

    clientSocket.send(str(uniqueId).encode(encoding='utf-8'))

    clients[uniqueId] = {'ip': clientAddress[0],
                         'port': clientAddress[1], 'state': 'connected'}

    print(
        f"New connection from {clientAddress}. Assigned ID: {uniqueId}. Number of clients is {numberOfClients}")

    while True:
        print(f'handling {uniqueId}')
        time.sleep(1)


if __name__ == "__main__":
    def signalHandler(signal, frame):
        serverSocket.close()
        sys.exit(1)

    signal.signal(signal.SIGINT, signalHandler)
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind((HOST, PORT))
    serverSocket.listen()

    print(f"Server listening on {HOST}:{PORT}")

    while True:
        clientSocket, clientAddr = serverSocket.accept()
        clientThread = threading.Thread(
            target=handleClient, args=(clientSocket, clientAddr))
        clientThread.start()
