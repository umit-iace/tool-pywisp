from threading import Thread
from collections import deque
from struct import pack
from socket import socket, AF_INET, SOCK_STREAM


class Sender(Thread):

    def __init__(self, connection, queue_size, msg_length):
        Thread.__init__(self)
        self.connection = connection
        self.deque = deque(maxlen=queue_size)
        self.msg_length = msg_length
        self._quit = False

    def run(self):
        while not self._quit:
            if len(self.deque) > 0:
                self.connection.send(self.deque.popleft())

    def send(self, id, data, format):
        id = pack('>B', id)
        args = [format] + [date for date in data]
        frame = pack(*args)
        msg = id + frame
        if len(msg) < self.msg_length + 1:
            for i in range(self.msg_length + 1 - len(msg)):
                msg += b'\x00'
        self.deque.append(msg)

    def quit(self):
        self._quit = True


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

    def receive(self):
        msg = self.deque.popleft()

        try:
            id = msg[0]
            data = msg[1:]

        except IndexError as e:
            print("Malformed message: ", msg)
            raise e

        return id, data

    def new_msg(self):
        return bool(len(self.deque))

    def quit(self):
        self._quit = True


def get_socket(init_port, np=4):
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


def establish_connection(socket, msg_length):
    print('waiting for a connection')
    connection, client_address = socket.accept()
    sender = Sender(connection, 1, msg_length)
    sender.start()
    receiver = Receiver(connection, None, msg_length)
    receiver.start()
    print('connection from', client_address)

    return connection, sender, receiver
