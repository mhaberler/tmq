import socket
from unittest import TestCase
from unittest.mock import MagicMock
from operator import attrgetter

from tmq import define as td
from tmq.tsocket import *
from tmq.context import Context

from .tools import *


class TestBroker(TestCase):
    def test_fake_broker(self):
        '''Pretend to act as a broker between two sockets'''
        pattern = td.pattern("test", "pattern")
        data = b'this is test data'

        addr_pub = ip, ports[0]
        addr_sub = ip, ports[1]
        addr_broker = ip, ports[2]

        broker = socket.socket()
        broker.bind(addr_broker)
        broker.listen(5)

        context = mock_context()
        pub = tmq_socket(context)
        sub = tmq_socket(context)

        tmq_bind(pub, addr_pub)
        tmq_bind(sub, addr_sub)

        tmq_broker(pub, addr_broker)
        tmq_broker(sub, addr_broker)

        tmq_subscribe(sub, pattern)
        # receive the request to be added to subscribers
        type, p, data = td.tmq_unpack(broker.accept()[0].recv(2048))
        self.assertEqual(p, pattern)
        addr, stype = td.tmq_unpack_address_t(data)
        self.assertEqual(addr, addr_sub)

        tmq_publish(pub, pattern)
        # receive the request to be added to publishers
        type, p, data = td.tmq_unpack(broker.accept()[0].recv(2048))
        self.assertEqual(p, pattern)
        addr, stype = td.tmq_unpack_address_t(data)
        self.assertEqual(addr, addr_pub)

        # send back subscriber addresses to publisher
        packed = td.tmq_pack(td.TMQ_PUB | td.TMQ_CACHE, pattern,
                             td.tmq_pack_address_t(*addr_sub))
        s = socket.socket()
        s.connect(addr_pub)
        s.send(packed)
        s.close();

        # receive addresses
        Context.process_tsocket(pub)
        self.assertSetEqual(pub.subscribed[pattern], set((addr_sub,)))

        # now send some data, no more broker necessary!
        tmq_send(pub, pattern, data)
        Context.process_tsocket(sub)
        result = tmq_recv(sub, pattern)

        self.assertEqual(data, result)

        close_all(pub, sub, broker)

    def test_broker(self):
        '''now do all of the above, but with a real broker'''
        pattern = td.pattern("test", "pattern")
        data = b'this is test data'

        addr_pub = ip, ports[0]
        addr_sub = ip, ports[1]
        addr_broker = ip, ports[2]

        context = mock_context()
        broker =    tmq_socket(context, td.TMQ_BROKER)
        pub =       tmq_socket(context)
        sub =       tmq_socket(context)

        tmq_bind(broker, addr_broker)
        tmq_bind(pub, addr_pub)
        tmq_bind(sub, addr_sub)

        tmq_broker(pub, addr_broker)
        tmq_broker(sub, addr_broker)

        # subscribe
        tmq_subscribe(sub, pattern)
        Context.process_tsocket(broker)
        self.assertEqual(broker.subscribed[pattern], set((addr_sub,)))

        # publish
        tmq_publish(pub, pattern)
        Context.process_tsocket(broker)
        self.assertEqual(broker.published[pattern], set((addr_pub,)))
        Context.process_tsocket(pub)
        self.assertEqual(pub.subscribed[pattern], set((addr_sub,)))

        # publish data
        tmq_send(pub, pattern, data)
        Context.process_tsocket(sub)
        result = tmq_recv(sub, pattern)
        self.assertEqual(data, result)

        close_all(pub, sub, broker)
        return
