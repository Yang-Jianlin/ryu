from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller import ofp_event
from ryu.ofproto import ofproto_v1_3
import socket


class L2Switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dp_id = '0'
        self.in_port = '0'

        # 开启client，并连接server
        self.client1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dst_host = '10.50.177.208'
        dst_port = 12345
        # 防止server端连接不上影响hub的使用
        try:
            self.client1.connect((dst_host, dst_port))
        except Exception as error:
            print('Connect error:', error)

    def doflow(self, datapath, command, priority, match, actions):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        req = ofp_parser.OFPFlowMod(datapath=datapath, command=command,
                                    priority=priority, match=match, instructions=inst)
        datapath.send_msg(req)

    # 控制器和交换机握手时，向交换机下发默认流表项
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        # add table-miss
        command = ofp.OFPFC_ADD
        match = ofp_parser.OFPMatch()
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.doflow(datapath, command, 0, match, actions)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser
        self.dp_id = dp.id

        # 计算出in_port
        start = str(msg).index('oxm_fields') + 11
        end = str(msg).index('),reason')
        inport_str = str(msg)[start:end]
        instr = eval(inport_str)
        self.in_port = instr['in_port']

        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
             data = msg.data
        print('id:{0}     in_port:{1}'.format(self.dp_id, self.in_port))
        # 每次有信息经过交换机时，控制器就将获取的dpid和port发送给server
        info = str(self.dp_id) + ',' + str(self.in_port)
        self.client1.send(info.encode())

        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=self.in_port,
            actions=actions, data=data)
        dp.send_msg(out)
