if __name__ != '__main__':
    exit(1)

import socket
import random
from threading import Thread, Lock
from time import sleep
import signal
import atomics


HOST = '127.0.0.1'
PORT = 5555

clients = {}
lock = Lock()
numberOfClients = 0

mustQuit = atomics.atomic(width=1, atype=atomics.UINT)
mustQuit.store(0)


def generateUniqueId() -> int:
    if numberOfClients > 999898:
        mustQuit.store(1)
        raise ValueError('Maximuum client count has been reached.')

    attemps = 0
    while True:
        newId = random.randint(100, 999999)
        if newId not in clients:
            return newId

        attemps += 1
        if attemps > 1000:
            break

    for i in range(100, 999999):
        if i not in clients:
            return i


def handleClient(clientSocket: socket.socket, clientAddress: tuple) -> None:
    global mustQuit
    global numberOfClients

    lock.acquire()
    uniqueId = generateUniqueId()
    clients[uniqueId] = {'ip': clientAddress[0],
                         'port': clientAddress[1],
                         'state': 'waiting-id',
                         'socket': clientSocket,
                         }

    numberOfClients += 1
    lock.release()

    for i in range(2):
        try:
            clientSocket.send(str(uniqueId).encode(encoding='utf-8'))
            break
        except:
            if i == 1:
                lock.acquire()
                del clients[uniqueId]
                numberOfClients -= 1
                lock.release()
                clientSocket.close()
            else:
                continue

    print(
        f'New connection: {clientAddress}. ID: {uniqueId}. Number of clients: {numberOfClients}')

    clientObject = clients[uniqueId]
    clientObject['state'] = 'idle'

    while True:
        sleep(0.01)

        if mustQuit.load() == 1:
            try:
                clientSocket.send('quit'.encode(encoding='utf-8'))
            except:
                clientSocket.close()
            clientSocket.close()
            break

        if clientObject['state'] == 'idle':
            # server receives the requested ID from the client
            mustBreak = False
            while True:
                if mustQuit.load() == 1:
                    try:
                        clientSocket.send('quit'.encode(encoding='utf-8'))
                    except:
                        pass

                    clientSocket.close()
                    mustBreak = True
                    break

                try:
                    requestedId = clientSocket.recv(1024).decode()
                    break

                except:
                    continue

            if mustBreak == True:
                lock.acquire()
                del clients[uniqueId]
                numberOfClients -= 1
                lock.release()
                clientSocket.close()
                break

            # Check if requestedId is a valid integer
            try:
                requestedId = int(requestedId)
            except ValueError:
                print(f'Invalid ID received from ID: {uniqueId}.')
                try:
                    clientSocket.send('-1'.encode(encoding='utf-8'))
                except:
                    lock.acquire()
                    del clients[uniqueId]
                    numberOfClients -= 1
                    lock.release()
                    clientSocket.close()
                    break

            # Check if the requested ID exists in clients and the client is idle
            if requestedId in clients and clients[requestedId]['state'] == 'idle':
                # Ask the client if they want to establish a connection
                try:
                    clients[requestedId]['socket'].send(
                        str(uniqueId).encode('utf-8'))
                except:
                    lock.acquire()
                    del clients[uniqueId]
                    numberOfClients -= 1
                    lock.release()
                    clientSocket.close()
                    break

                while True:
                    try:
                        response = clients[requestedId]['socket'].recv(
                            1024).decode()
                        break
                    except:
                        continue

                if response == 'yes':
                    # Establish connection
                    clientObject['state'] = 'connected'
                    clients[requestedId]['state'] = 'connected'
                    print(
                        f'Connection established between {uniqueId} and {requestedId}')

                else:
                    print(f'Connection request denied by {uniqueId}')
                    try:
                        clientSocket.send('0'.encode('utf-8'))
                    except:
                        lock.acquire()
                        del clients[uniqueId]
                        numberOfClients -= 1
                        lock.release()
                        clientSocket.close()
                        break

                    break
            else:
                try:
                    clientSocket.send('-1'.encode('utf-8'))
                except:
                    lock.acquire()
                    del clients[uniqueId]
                    numberOfClients -= 1
                    lock.release()
                    clientSocket.close()
                    break


def socketHandler(serverSocket):
    global mustQuit

    clientThreads = []
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSocket.bind((HOST, PORT))
    serverSocket.listen()
    print(f'Server listening on {HOST}:{PORT}')

    while True:
        try:
            clientSocket, clientAddr = serverSocket.accept()
            clientThread = Thread(
                target=handleClient, args=(clientSocket, clientAddr))
            clientThread.daemon = True
            clientThreads.append(clientThread)
            clientThread.start()
        except:
            if mustQuit.load() == 1:
                for thread in clientThreads:
                    thread.join()
                break


socket.setdefaulttimeout(2)
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socketThread = Thread(target=socketHandler, args=(serverSocket,))
socketThread.start()


def signalHandler(sig, frame):
    global mustQuit
    mustQuit.store(1)
    print(
        f'[MAIN]: SIGINT received! All threads will terminate in short period of time.')
    exit(1)


signal.signal(signal.SIGINT, signalHandler)
while True:
    sleep(0.1)
