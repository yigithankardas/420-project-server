if __name__ != '__main__':
    exit(1)

import socket
import random
from threading import Thread, Lock
from time import sleep
import signal
import atomics
import random
from cryptography.hazmat.primitives.asymmetric import dh


HOST = '127.0.0.1'
PORT = 5555

SOCKET_TIMEOUT = 0.5
SERVER_THREAD_WAIT = 0.01

clients = {}
lock = Lock()
numberOfClients = 0

# Diffie Hellman Parameters
parameters = dh.generate_parameters(generator=2, key_size=512)
p = parameters.parameter_numbers().p
g = parameters.parameter_numbers().g

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
    clientEntry = {'ip': clientAddress[0],
                   'port': clientAddress[1],
                   'id': generateUniqueId(),
                   'state': 'waiting-id',
                   'socket': clientSocket,
                   'connectedId': -1,
                   'canRead': atomics.atomic(width=1, atype=atomics.UINT)
                   }

    clients[clientEntry['id']] = clientEntry
    clients[clientEntry['id']]['canRead'].store(1)
    numberOfClients += 1
    lock.release()

    uniqueId = clientEntry['id']
    try:
        clientSocket.send(
            (str(uniqueId)+'\0').encode(encoding='utf-8'))
        clientSocket.send(f"G-{g}\0P-{p}\0".encode(encoding='utf-8'))
    except:
        lock.acquire()
        del clients[uniqueId]
        numberOfClients -= 1
        lock.release()
        clientSocket.close()

    print(
        f'New connection: {clientAddress}. ID: {uniqueId}. Number of clients: {numberOfClients}')

    clientEntry['state'] = 'idle'

    while True:
        sleep(SERVER_THREAD_WAIT)

        isMessageAnImage = False
        chunks = []
        uniqueId = clientEntry['id']
        if clientEntry['canRead'].load() == 0:
            continue

        if mustQuit.load() == 1:
            try:
                clientSocket.send('quit\0'.encode(encoding='utf-8'))
            except:
                clientSocket.close()
            finally:
                clientSocket.close()
            break

        try:
            message = clientSocket.recv(4096)
            if b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' in message:
                control = b''
                for _ in range(len(message)):
                    control += b'\x00'
                if control == message:
                    newMessage = b''
                    chunkCount = len(message)
                    isMessageAnImage = True
                    clientSocket.send(message)
                    for _ in range(chunkCount):
                        bytes = clientSocket.recv(2000)
                        newMessage += bytes
                        chunks.append(bytes)
                        clientSocket.send(message)
                    message = newMessage
        except:
            continue

        if clientEntry['state'] != 'in-session':
            message = message.decode()

        if message == 'quit':
            lock.acquire()
            del clientEntry
            numberOfClients -= 1
            lock.release()
            clientSocket.close()
            print(f'[T-{uniqueId}]: Connection has been terminated.')
            break

        if clientEntry['state'] == 'idle':
            # server receives the requested ID from the client
            # Check if requestedId is a valid integer

            try:
                requestedId = int(message)
            except ValueError:
                print(f'[T-{uniqueId}]: Invalid ID received.')
                try:
                    clientSocket.send('-2\0'.encode(encoding='utf-8'))
                    continue
                except:
                    lock.acquire()
                    del clientEntry
                    numberOfClients -= 1
                    lock.release()
                    clientSocket.close()
                    break

            # Check if the requested ID exists in clients and the client is idle
            if requestedId in clients and clients[requestedId]['state'] == 'idle':
                # Ask the client if they want to establish a connection
                clients[requestedId]['canRead'].store(0)
                try:
                    clients[requestedId]['socket'].send(
                        f'S-{uniqueId}\0'.encode('utf-8'))
                except:
                    try:
                        clientSocket.send('-1\0'.encode('utf-8'))
                        continue
                    except:
                        lock.acquire()
                        del clientEntry
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
                    clientEntry['state'] = 'connected'
                    clients[requestedId]['state'] = 'connected'

                    clientEntry['state'] = 'key-exchange'
                    clients[requestedId]['state'] = 'key-exchange'
                    try:
                        clientSocket.send('1\0'.encode('utf-8'))
                        clients[requestedId]['socket'].send(
                            '1\0'.encode('utf-8'))

                        clientEntry['connectedId'] = requestedId
                        clients[requestedId]['connectedId'] = uniqueId

                        gA = clientSocket.recv(1024).decode()
                        gB = clients[requestedId]['socket'].recv(1024).decode()

                        clientSocket.send(f'B-{gB}\0'.encode('utf-8'))
                        clients[requestedId]['socket'].send(
                            f'B-{gA}\0'.encode('utf-8'))

                        clientEntry['state'] = 'in-session'
                        clients[requestedId]['state'] = 'in-session'
                        clients[requestedId]['canRead'].store(1)

                    except:
                        clientEntry['state'] = 'idle'
                        clients[requestedId]['state'] = 'idle'
                        newUniqueID = generateUniqueId()
                        newRequestedID = generateUniqueId()
                        clients[newUniqueID] = clients.pop(uniqueId)
                        clients[newRequestedID] = clients.pop(requestedId)
                        clients[newUniqueID]['id'] = newUniqueID
                        clients[newRequestedID]['id'] = newRequestedID
                        clients[newRequestedID]['canRead'].store(1)
                        try:
                            clientSocket.send('-1\0'.encode('utf-8'))
                            clientSocket.send(
                                f'newID-{newUniqueID}\0'.encode('utf-8'))
                            clients[newRequestedID]['socket'].send(
                                f'newID-{newRequestedID}\0'.encode('utf-8'))
                        except:
                            lock.acquire()
                            del clients[uniqueId]
                            numberOfClients -= 1
                            lock.release()
                            clientSocket.close()
                            break

                        continue
                    print(
                        f'[T-{uniqueId}]: Connection established between {uniqueId} and {requestedId}')

                elif response == 'no':
                    print(f'[T-{uniqueId}]: Connection request denied')
                    newUniqueID = generateUniqueId()
                    newRequestedID = generateUniqueId()
                    clients[newUniqueID] = clients.pop(uniqueId)
                    clients[newRequestedID] = clients.pop(requestedId)
                    clients[newUniqueID]['id'] = newUniqueID
                    clients[newRequestedID]['id'] = newRequestedID
                    clients[newRequestedID]['canRead'].store(1)
                    try:
                        clientSocket.send('-1\0'.encode('utf-8'))
                        clientSocket.send(
                            f'newID-{newUniqueID}\0'.encode('utf-8'))
                        clients[newRequestedID]['socket'].send(
                            f'newID-{newRequestedID}\0'.encode('utf-8'))

                    except:
                        lock.acquire()
                        del clients[uniqueId]
                        numberOfClients -= 1
                        lock.release()
                        clientSocket.close()
                        break

            else:
                try:
                    clientSocket.send('-1\0'.encode('utf-8'))
                    newUniqueID = generateUniqueId()
                    clients[newUniqueID] = clients.pop(uniqueId)
                    clients[newUniqueID]['id'] = newUniqueID
                    clientSocket.send(f'newID-{newUniqueID}\0'.encode('utf-8'))
                except:
                    lock.acquire()
                    del clients[uniqueId]
                    numberOfClients -= 1
                    lock.release()
                    clientSocket.close()
                    break

        elif clientEntry['state'] == 'in-session':
            if isMessageAnImage:
                clients[clientEntry['connectedId']]['canRead'].store(0)
                sleep(0.4)

            if (message == b'quit'):
                lock.acquire()
                del clients[uniqueId]
                numberOfClients -= 1
                lock.release()
                clientSocket.close()
                connectedClientId = clientEntry['connectedId']
                clients[connectedClientId]['state'] = 'idle'
                connectedClientSocket = clients[connectedClientId]['socket']
                connectedClientSocket.send(f'disconnected\0'.encode('utf-8'))
                newUniqueID = generateUniqueId()
                clients[newUniqueID] = clients.pop(connectedClientId)
                clients[newUniqueID]['id'] = newUniqueID
                clients[newUniqueID]['connectedId'] = -1
                connectedClientSocket.send(
                    f'newID-{newUniqueID}\0'.encode('utf-8'))
                clients[newUniqueID]['canRead'].store(1)
                break

            print(
                f'[T-{uniqueId}]: Message has been received from {clientEntry["connectedId"]}')

            connectedClientId = clientEntry['connectedId']
            connectedClientSocket = clients[connectedClientId]['socket']

            try:
                if isMessageAnImage:
                    chunkCountBytes = b''
                    for _ in range(len(chunks)):
                        chunkCountBytes += b'\x00'

                    connectedClientSocket.send(chunkCountBytes)
                    connectedClientSocket.recv(len(chunkCountBytes))
                    for chunk in chunks:
                        connectedClientSocket.send(chunk)
                        connectedClientSocket.recv(len(chunkCountBytes))
                    clients[connectedClientId]['canRead'].store(1)
                else:
                    connectedClientSocket.send(message)
            except:
                if isMessageAnImage:
                    clients[connectedClientId]['canRead'].store(1)
                continue


def socketHandler(serverSocket):
    global mustQuit

    clientThreads = []
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSocket.bind((HOST, PORT))
    serverSocket.listen()
    print(f'[SERVER]: Listening on {HOST}:{PORT}')

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


socket.setdefaulttimeout(SOCKET_TIMEOUT)
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
while mustQuit.load() != 1:
    sleep(0.01)

socketThread.join()
