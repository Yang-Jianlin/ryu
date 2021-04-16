from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller.handler import set_ev_cls
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.lib.packet import packet
from ryu.lib import pcaplib

'''
wireshark wiki数据的解析与写入
'''


class Wikipcap(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pcap_writer = pcaplib.Writer(open('pcapdata.pcap', 'wb'))

    # 将收到的数据输出到pcap文件中
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        # msf.data就是发送过来的数据包，从中可以解析出协议、源ip、mac地址等信息
        print('msg.data:', msg.data)
        self.pcap_writer.write_pkt(msg.data)

    # 将pcap的数据读取出来，输出
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def parser_pcap(self, filename):
        frame_count = 0
        for ts, buf in pcaplib.Reader(open('data.pcap', 'rb')):
            frame_count += 1
            pkt = packet.Packet(buf)
            print("%d, %f, %s" % (frame_count, ts, pkt))
