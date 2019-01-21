import random
import socket
import threading as thg
import time
import unittest as ut
from queue import Queue

from ..connection import TcpConnection


class myServer(thg.Thread):
    def __init__(self, threadID, name, address):
        thg.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.servs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.servs.bind(address)
        self.servs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.servs.listen(1)

    def run(self):
        self.conn, self.claddr = self.servs.accept()
        print('Connected with ', self.claddr)
        while 1:
            try:
                self.conn.send(b'\x32')
            except:
                break
            try:
                data = self.conn.recv(1)
            except:
                break
            if data == b'\x32':
                break
            time.sleep(0.001)
        self.conn.close()


class TestTcpConnection(ut.TestCase):
    def setUp(self):
        # set up test host
        self.server_ip = '127.0.0.1'
        self.server_port = random.randint(50000, 50050)
        self.thread_server = myServer(1, "Server thread", (self.server_ip, self.server_port))
        print("\nServer listening...\n")
        # set up client which should get tested
        self.inputQueue = Queue()
        self.outputQueue = Queue()
        self.connection_tcp = TcpConnection(self.inputQueue, self.outputQueue,
                                            self.server_port, self.server_ip)
        self.thread_server.start()

    def tearDown(self):
        # close client connection
        self.connection_tcp.disconnect()

    def test_connection(self):
        returnvalue = self.connection_tcp.connect()
        self.assertEqual(returnvalue, True,
                         "Can't connect to server!")
        data = {'id': 1, 'msg': b'\x37'}
        self.inputQueue.put(data)
        data = {'id': 1, 'msg': b'\x38'}
        self.inputQueue.put(data)
        self.connection_tcp.run()

    def test_disconnect(self):
        returnvalue = self.connection_tcp.connect()
        self.assertEqual(returnvalue, True,
                         "Can't connect to server!")
        self.connection_tcp.disconnect()


if __name__ == '__main__':
    suite = ut.TestLoader().loadTestsFromTestCase(TestTcpConnection)
    ut.TextTestRunner(verbosity=2).run(suite)
