from collections import deque
import time

from socket import socket, AF_INET, SOCK_STREAM
from struct import pack
from threading import Thread


class Sender:

    def __init__(self, connection, queueSize, msgLength, minWaitTime=0.009):
        self.connection = connection
        self.deque = deque(maxlen=queueSize)
        self.msgLength = msgLength
        self.minWaitTime = minWaitTime
        self.lastSendAll = time.time()

    def put(self, id, data, format):
        id = pack('>B', id)
        args = [format] + [date for date in data]
        frame = pack(*args)
        msg = id + frame
        if len(msg) < self.msgLength + 1:
            for i in range(self.msgLength + 1 - len(msg)):
                msg += b'\x00'
        self.deque.append(msg)

    def send_all(self):
        t = time.time()
        if t - self.lastSendAll >= self.minWaitTime:
            self.lastSendAll = t
            while len(self.deque):
                self.connection.send(self.deque.popleft())


class Receiver(Thread):

    def __init__(self, connection, queue_size, msg_length):
        Thread.__init__(self)
        self.connection = connection
        self.deque = deque(maxlen=queue_size)
        self.msg_length = msg_length
        self._quit = False

    def run(self):
        while not self._quit:
            self.deque.append(self.connection.recv(self.msg_length))

    def getAll(self):
        msgs = list()
        while self.newMsg():
            msgs.append(self.getMsg())

        return msgs

    def getMsg(self):
        msg = self.deque.popleft()

        try:
            id = msg[0]
            data = msg[1:]
            print("received (id, data): ({}, {})".format(id, data))

        except IndexError as e:
            print("Malformed message: ", msg)
            raise e

        return id, data

    def newMsg(self):
        return bool(len(self.deque))

    def quit(self):
        self._quit = True


def socket_bind_listen(init_port, np=4):
    bound = False
    port = init_port

    while not bound and port - init_port < np:
        try:
            sock = socket(AF_INET, SOCK_STREAM)
            server_address = ('localhost', port)
            sock.bind(server_address)
            bound = True

        except OSError:
            port = port + 1

    print('starting up on {} port {}'.format(*server_address))
    sock.listen(1)

    return sock


def socket_accept(socket):
    print('waiting for a connection')
    connection, client_address = socket.accept()
    print('connection from', client_address)

    return connection


def get_sender_receiver(connection, msg_length):
    sender = Sender(connection, 1, msg_length)
    receiver = Receiver(connection, None, msg_length)
    receiver.start()

    return sender, receiver
