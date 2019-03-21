from collections import deque

from socket import socket, AF_INET, SOCK_STREAM
from struct import pack
from threading import Thread


class Sender:
    """
    Realizes a Tcp/IP transmitter.
    """
    def __init__(self, connection, queueSize, msgLength):
        self.connection = connection
        self.deque = deque(maxlen=queueSize)
        self.msgLength = msgLength

    def put(self, id, data, format):
        """
        Sends message with given id and payload to queue.
        :param id: id of frame
        :param data: payload of frame
        :param format: byte format of payload
        """
        id = pack('>B', id)
        args = [format] + [date for date in data]
        frame = pack(*args)
        msg = id + frame
        if len(msg) < self.msgLength + 1:
            for i in range(self.msgLength + 1 - len(msg)):
                msg += b'\x00'
        self.deque.append(msg)

    def sendAll(self):
        """
        Sends all messages from queue to connected client
        """
        while len(self.deque):
            self.connection.send(self.deque.popleft())


class Receiver(Thread):
    """
    Realizes a Tcp/IP receiver as thread.
    """
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
        """
        Returns all received messages as list .
        :return: list of messages
        """
        msgs = list()
        while self.newMsg():
            msgs.append(self.getMsg())

        return msgs

    def getMsg(self):
        """
        Splits received message in id and payload part.
        :return: id and payload
        """
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
        """
        Checks if messages in queue.
        :return: True if a message is available otherwise False
        """
        return bool(len(self.deque))

    def quit(self):
        self._quit = True


def socketBindListen(initPort, np=4):
    """
    Initialize a socket with given port.
    :param initPort: first port address
    :param np: port changes
    :return: socket instance
    """
    bound = False
    port = initPort

    while not bound and port - initPort < np:
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


def socketAccept(socket):
    """
    Waiting for a client accept at socket
    :param socket: listening socket
    :return: connection instance for connected client
    """
    print('waiting for a connection')
    connection, client_address = socket.accept()
    print('connection from', client_address)

    return connection


def getSenderReceiver(connection, msgLength):
    """
    Initializes the transmitter and receiver for a given connection.
    :param connection: Tcp/IP connection instance
    :param msgLength: length of message
    :return: transmitter and receiver instance
    """
    sender = Sender(connection, 1, msgLength)
    receiver = Receiver(connection, None, msgLength)
    receiver.start()

    return sender, receiver
