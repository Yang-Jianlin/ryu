import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER, HANDSHAKE_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3
from ryu.topology.switches import LLDPPacket
from ryu.base.app_manager import lookup_service_brick

# 导入这些主要是为了让网络链路中产生LLDP数据包，只有产生了LLDP数据报，才能进行LLDP时延探测
from ryu.topology.api import get_switch, get_link, get_host


class DelayDetector(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DelayDetector, self).__init__(*args, *kwargs)
        self.name = 'delay_detector'
        self.switches = lookup_service_brick('switches')
        # 存储网络拓扑的交换机id
        self.dpidSwitch = {}
        # 存储echo往返时延
        self.echoDelay = {}
        # 存储LLDP时延
        self.src_dstDelay = {}

        # 实现协程，进行时延的周期探测
        self.detector_thread = hub.spawn(self.detector)

    # 每隔3秒进行控制器向交换机发送一次echo报文，用以获取往返时延
    def detector(self):
        while True:
            self.send_echo_request()
            hub.sleep(3)

    def add_flow(self, datapath, priority, match, actions):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        command = ofp.OFPFC_ADD
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        req = ofp_parser.OFPFlowMod(datapath=datapath, command=command,
                                    priority=priority, match=match, instructions=inst)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        # add table-miss
        match = ofp_parser.OFPMatch()
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(datapath=datapath, priority=0, match=match, actions=actions)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.dpidSwitch:
                self.dpidSwitch[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.dpidSwitch:
                del self.dpidSwitch[datapath.id]

    # 由控制器向交换机发送echo报文，同时记录此时时间
    def send_echo_request(self):
        # 循环遍历交换机，逐一向存在的交换机发送echo探测报文
        for datapath in self.dpidSwitch.values():
            parser = datapath.ofproto_parser
            echo_req = parser.OFPEchoRequest(datapath, data=bytes("%.12f" % time.time(), encoding="utf8"))  # 获取当前时间

            datapath.send_msg(echo_req)
            # 每隔0.5秒向下一个交换机发送echo报文，防止回送报文同时到达控制器
            hub.sleep(0.5)

    # 交换机向控制器的echo请求回应报文，收到此报文时，控制器通过当前时间-时间戳，计算出往返时延
    @set_ev_cls(ofp_event.EventOFPEchoReply, [MAIN_DISPATCHER, CONFIG_DISPATCHER, HANDSHAKE_DISPATCHER])
    def echo_reply_handler(self, ev):
        now_timestamp = time.time()
        try:
            echo_delay = now_timestamp - eval(ev.msg.data)
            # 将交换机对应的echo时延写入字典保存起来
            self.echoDelay[ev.msg.datapath.id] = echo_delay
            print('*******************echo delay*****************')
            print(self.echoDelay)
        except Exception as error:
            print(error)
            return

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):  # 处理到达的LLDP报文，从而获得LLDP时延
        msg = ev.msg
        try:
            src_dpid, src_outport = LLDPPacket.lldp_parse(msg.data)  # 获取两个相邻交换机的源交换机dpid和port_no(与目的交换机相连的端口)
            dst_dpid = msg.datapath.id  # 获取目的交换机（第二个），因为来到控制器的消息是由第二个（目的）交换机上传过来的
            if self.switches is None:
                self.switches = lookup_service_brick("switches")  # 获取交换机模块实例

            # 获得key（Port类实例）和data（PortData类实例）
            for port in self.switches.ports.keys():  # 开始获取对应交换机端口的发送时间戳
                if src_dpid == port.dpid and src_outport == port.port_no:  # 匹配key
                    port_data = self.switches.ports[port]  # 获取满足key条件的values值PortData实例，内部保存了发送LLDP报文时的timestamp信息
                    timestamp = port_data.timestamp
                    if timestamp:
                        delay = time.time() - timestamp
                        self._save_delay_data(src=src_dpid, dst=dst_dpid, src_port=src_outport, lldp_dealy=delay)
        except Exception as error:
            print(error)
            return

    def _save_delay_data(self, src, dst, src_port, lldp_dealy):
        key = "%s-%s-%s" % (src, src_port, dst)
        self.src_dstDelay[key] = lldp_dealy
        print('------------------lldp delay--------------------')
        print(self.src_dstDelay)
