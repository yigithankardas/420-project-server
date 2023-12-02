if __name__ != "__main__":
    exit(1)

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
    global mustClose
    global numberOfClients
    uniqueId = generateUniqueId()
    clients[uniqueId] = {'ip': clientAddress[0],
                         'port': clientAddress[1], 'state': 'waiting-ID'}
    
    numberOfClients += 1
    clientSocket.send(str(uniqueId).encode(encoding='utf-8'))

    print(
        f"New connection from {clientAddress}. Assigned ID: {uniqueId}. Number of clients is {numberOfClients}")
    clients[uniqueId]['state'] = 'idle'
    while True:
        if mustClose == True:
            clientSocket.close()
            break
        # server recieve the requestdID from client
        if clients[uniqueId]['state'] == 'idle':
            # server receives the requested ID from the client
            try:
              requestedId = clientSocket.recv(1024).decode()
            except:
                break
            # Check if requestedId is a valid integer
            try:
                requestedId = int(requestedId)
            except ValueError:
                print(f"Invalid ID received from {clientAddress}. Closing connection.")
                break

            # Check if the requested ID exists in clients and the client is idle
            if requestedId in clients and clients[requestedId]['state'] == 'idle':
                # Ask the client if they want to establish a connection
                clientSocket.send(uniqueId.encode('utf-8'))
                response = clientSocket.recv(1024).decode().lower()

                if response == "yes":
                    # Establish connection
                    clients[uniqueId]['state'] = 'connected'
                    clients[requestedId]['state'] = 'connected'
                    print(f"Connection established between {uniqueId} and {requestedId}")

                else:
                    print(f"Connection request denied by {uniqueId}")
                    break
            else:
                # ID not found or client is not idle
                print("sa2")
                clientSocket.send("-1".encode('utf-8'))

        time.sleep(0.1)


mustClose = False

def socketHandler(serverSocket):
    global mustClose
    clientThreads = []
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSocket.bind((HOST, PORT))
    serverSocket.listen()
    print(f"Server listening on {HOST}:{PORT}")
    while True:
        try:
            clientSocket, clientAddr = serverSocket.accept()
            clientThread = threading.Thread(
                target=handleClient, args=(clientSocket, clientAddr))
            clientThread.daemon = True
            clientThreads.append(clientThread)
            clientThread.start()
        except:
            if mustClose == True:
                for thread in clientThreads:
                    thread.join()
                break

socket.setdefaulttimeout(2)
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socketThread = threading.Thread(target=socketHandler, args=(serverSocket,))
socketThread.start()

def signalHandler(sig, frame):
    global mustClose
    mustClose = True
    print(f'[MAIN]: SIGINT received! All threads will terminate in short period of time. mustClose: {mustClose}')
    exit(1)

signal.signal(signal.SIGINT, signalHandler)
while True:
    time.sleep(0.1)
