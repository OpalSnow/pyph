import itertools

import numpy
from asyncio.queues import Queue, QueueEmpty

from .len_packet import LenPackets
from .xor import XorInOut
from .gs_l2_packet import PacketError


class Connect():
    def __init__(self, name, packet):
        from l2.len_packet import LenPackets
        from l2.xor import XorInOut
        self.name = name
        self._data = b''
        self.q = Queue()
        self.command_stack = [] # func(gen: types.GeneratorType) -> types.GeneratorType
        self.pck_len = LenPackets()
        self.xor = XorInOut(packet)
        self.pipe = PacketPipe(packet, self)


class PacketPipe():
    def __init__(self, packet, connect):
        self.packet = packet
        self.connect = connect
        self.gameapi = packet.manager.gameapi
        if self.connect.name == 'server': # c -> s
            self.pck_func = [self.key_packet_initialization, ]
        else: # s -> c
            self.pck_func = []


    def run(self, pck_gen):
        for f in self.pck_func:
            pck_gen = f(pck_gen)
        return pck_gen

    def key_packet_initialization(self, pck_gen):
        for gen in pck_gen:
            if gen:
                self.packet.client.pck_func = self.packet.server.pck_func = [
                    self.pck_len_in,
                    self.pck_xor_in,
                    self.pck_get_data,
                    self.pck_manager,
                    self.pck_xor_out,
                    self.pck_len_out,
                ]
            yield gen

    def pck_len_in(self, pck_gen):
        yield from self.connect.pck_len.pck_in(pck_gen)

    def pck_len_out(self, pck_gen):
        yield from self.connect.pck_len.pck_out(pck_gen)

    def pck_xor_in(self, pck_gen):
        yield from self.connect.xor.pck_in(pck_gen)

    def pck_xor_out(self, pck_gen):
        yield from self.connect.xor.pck_out(pck_gen)

    def pck_get_data(self, pck_gen):
        name=self.connect.name
        peername=self.packet.peername
        for packet in pck_gen:
            print(packet)
            try:
                unpack = self.gameapi.unpack(packet, name)
                if isinstance(unpack, numpy.ndarray):
                    print('up/', name[0:1],'->', unpack)
                yield packet
            except PacketError:
                print('error parsing packet {}: {}'.format(name, packet))
                yield packet

    def pck_manager(self, pck_gen):
        yield from self.packet.manager(
            self.connect.name, pck_gen, self.packet.peername)