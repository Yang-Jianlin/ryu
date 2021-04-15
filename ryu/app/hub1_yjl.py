from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller import ofp_event
from ryu.ofproto import ofproto_v1_3
'''
实现了一个hub的功能，
即控制器通过packet_in数据包的解析，进行命令的下发，
这个程序的一切指令处理均在控制器进行，并不会进行流表的下发，只会下发转发指令，
所以，在运行之前需要手动在ovs上添加默认controller的流表
'''


class L2Switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser
        dp_id = dp.id

        # 计算出in_port
        start = str(msg).index('oxm_fields') + 11
        end = str(msg).index('),reason')
        inport_str = str(msg)[start:end]
        instr = eval(inport_str)
        in_port = instr['in_port']

        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
             data = msg.data
        print('id:{0}'.format(dp_id))
        print('in_port:{0}'.format(in_port))

        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=data)
        dp.send_msg(out)
