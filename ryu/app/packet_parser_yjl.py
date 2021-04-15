import array

from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller.handler import set_ev_cls
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.lib.packet import packet
'''
实现了数据包的解析功能
即：控制器从交换机收到数据之后，对数据进行解析
提取出协议，目的ip，源ip等信息
'''


class Pktparser(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        # msf.data就是发送过来的数据包，从中可以解析出协议、源ip、mac地址等信息
        print('msg.data:', msg.data)
        pkt = packet.Packet(array.array('B', msg.data))
        # 几种协议
        pName = []
        for p in pkt.protocols:
            print('received protocol data:', p)
            pName.append(p.protocol_name)
            if p.protocol_name == 'arp':
                print('src_ip: {0}, dst_ip: {1}'.format(p.src_ip, p.dst_ip))
        print('protocol category:', pName)
