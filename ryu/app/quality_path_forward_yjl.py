import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER, HANDSHAKE_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3
from ryu.topology.switches import LLDPPacket
from ryu.base.app_manager import lookup_service_brick
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet

# 导入这些主要是为了让网络链路中产生LLDP数据包，只有产生了LLDP数据报，才能进行LLDP时延探测
from ryu.topology.api import get_switch, get_link, get_host
from ryu.topology import event, switches

# networkx用于存储链路信息，本程序存储为一个有向图
import networkx as nx


class DelayDetector(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DelayDetector, self).__init__(*args, *kwargs)
        self.name = 'delay_detector'
        self.switches = lookup_service_brick('switches')
        # 初始化networkx的有向图
        self.G = nx.DiGraph()
        self.topology_api_app = self

        # 存储网络拓扑的交换机id
        self.dpidSwitch = {}
        # 存储echo往返时延
        self.echoDelay = {}
        # 存储LLDP时延
        self.src_dstDelay = {}
        # 存储链路的时延，即LLDP时延-echo的时延，计算出的每条链路的时延
        self.link_Delay = {}

        # 存储源-目的-权重(时延)的列表，用于向有向图写入边信息
        self.links_src_dst = []
        # 存储整个链路各个节点之间的连接信息，包括源端口，
        # 例如s1-s2，通过s1的2端口连接，存储的信息即为：{’1-2‘：2}
        self.id_port = {}

        # 实现协程，进行时延的周期探测
        self.detector_thread = hub.spawn(self.detector)

    # 每间隔三秒，进行如下操作：
    # 控制器向交换机发送一次echo报文，用以获取往返时延
    # echo时延知道后，计算各个链路的时延，即LLDP-echo时延
    # 根据各个链路的时延更新网络拓扑有向图的每条边的权重
    def detector(self):
        while True:
            self.send_echo_request()
            self.link_delay()
            self.update_topo()
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

    events = [event.EventSwitchEnter, event.EventSwitchLeave,
              event.EventSwitchReconnected,
              event.EventPortAdd, event.EventPortDelete,
              event.EventPortModify,
              event.EventLinkAdd, event.EventLinkDelete]

    # 获取网络链路拓扑
    # 即将节点和边信息写入有向图中，默认的权重为0
    @set_ev_cls(events)
    def get_topo(self, ev):
        switch_list = get_switch(self.topology_api_app)
        topo_switches = []
        # 得到每个设备的id，并写入图中作为图的节点
        for switch in switch_list:
            topo_switches.append(switch.dp.id)
        self.G.add_nodes_from(topo_switches)

        link_list = get_link(self.topology_api_app)
        self.links_src_dst = []
        # 将得到的链路的信息作为边写入图中
        # 注意这里links_src_dst时列表里列表，即[[],[],[]]，不能是元组，因为元组不可更改，也就是后面无法更新权重信息
        for link in link_list:
            self.links_src_dst.append([link.src.dpid, link.dst.dpid, 0])
        self.G.add_weighted_edges_from(self.links_src_dst)

        for link in link_list:
            self.links_src_dst.append([link.dst.dpid, link.src.dpid, 0])
        self.G.add_weighted_edges_from(self.links_src_dst)

    # 更新拓扑信息，主要更新有向图的边的权重
    # 即，程序获取链路的实时时延，当时延变化时，就将新的时延作为权重写入有向图中
    def update_topo(self):
        # [[1, 2, 0], [3, 2, 0], [2, 1, 0], [2, 3, 0], [2, 1, 0], [2, 3, 0], [1, 2, 0], [3, 2, 0]]
        # {'2-3-3': 0.000362396240234375, '2-2-1': 0.001207113265991211, '1-2-2': 0.0004553794860839844, '3-2-2': 0.00015854835510253906}
        # 将link_Delay的时延作为权重更新进links_src_dst列表中，然后更新入有向图
        for key in self.link_Delay:
            list = key.split('-')
            l = (int(list[0]), int(list[2]))
            for i in self.links_src_dst:
                if l == (i[0], i[1]):
                    i[2] = self.link_Delay[key]

        self.G.add_weighted_edges_from(self.links_src_dst)

    # 获取输出的端口，这里的输出端口是控制器指示数据转发时按照最短权重获得的输出端口进行数据转发
    def get_out_port(self, datapath, src, dst, in_port):
        global out_port
        dpid = datapath.id

        # 开始时，各个主机可能在图中不存在，因为开始ryu只获取了交换机的dpid，并不知道各主机的信息，
        # 所以需要将主机存入图中
        # 同时将记录主机和交换机之间的连接关系和端口
        if src not in self.G:
            self.G.add_node(src)
            self.G.add_weighted_edges_from([[dpid, src, 0]])
            self.G.add_weighted_edges_from([[src, dpid, 0]])
            src_dst = "%s-%s" % (dpid, src)
            self.id_port[src_dst] = in_port

        # 计算出基于最小权重的链路，按照这个转发链路进行数据的转发
        if dst in self.G:
            path = nx.shortest_path(self.G, src, dst, weight='weight')
            next_hop = path[path.index(dpid) + 1]
            for key in self.id_port:
                match_key = "%s-%s" % (dpid, next_hop)
                if key == match_key:
                    out_port = self.id_port[key]
                    # print('key_out_port:', out_port)
            print(path)
        else:
            out_port = datapath.ofproto.OFPP_FLOOD
        return out_port

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
        except Exception as error:
            print("echo error:", error)
            return

    # 处理由交换机到来的消息，如LLDP消息和数据转发的消息
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        dpid = datapath.id
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        # try...except，由于packetin中存在LLDP消息和主机的数据转发消息，
        # 二者格式不一样，所以用try...except进行控制，分别处理两种消息；
        try:  # 处理到达的LLDP报文，从而获得LLDP时延
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
        except Exception as error:  # 处理到达的主机的转发消息
            out_port = self.get_out_port(datapath, src, dst, in_port)
            actions = [ofp_parser.OFPActionOutput(out_port)]

            # 这里如果使用add_flow()进行了流表的添加，那么程序中的实时更新拓扑的权重就无意义了，转发就会依据流表进行
            # 所以这里不使用add_flow()方法，而是采用hub的形式，也就是每次转发都会请求控制器进行实时计算链路质量

            # 如果执行的动作不是flood，那么此时应该依据流表项进行转发操作，所以需要添加流表到交换机
            # if out_port != ofp.OFPP_FLOOD:
            #     match = ofp_parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            #     self.add_flow(datapath=datapath, priority=1, match=match, actions=actions)

            data = None
            if msg.buffer_id == ofp.OFP_NO_BUFFER:
                data = msg.data
            # 控制器指导执行的命令
            out = ofp_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                          in_port=in_port, actions=actions, data=data)
            datapath.send_msg(out)

    # 用于存储各个LLDP的时延
    # 同时记录拓扑中各个交换机之间的连接
    def _save_delay_data(self, src, dst, src_port, lldp_dealy):
        key = "%s-%s-%s" % (src, src_port, dst)
        src_dst = "%s-%s" % (src, dst)
        self.id_port[src_dst] = src_port
        # {'1-2': 2, '3-2': 2, '2-1': 2, '2-3': 3}
        self.src_dstDelay[key] = lldp_dealy

    # 计算链路的时延
    def link_delay(self):
        for key in self.src_dstDelay:
            list = key.split('-')
            t1 = 0
            t2 = 0
            for key_s in self.echoDelay:
                if key_s == int(list[0]):
                    t1 = self.echoDelay[key_s]
                if key_s == int(list[2]):
                    t2 = self.echoDelay[key_s]
            delay = self.src_dstDelay[key] - (t1 + t2) / 2
            # 由于误差及其他原因，可能出现时延为负值情况，如果为负值就不要进行时延的更新
            if delay >= 0:
                self.link_Delay[key] = self.src_dstDelay[key] - (t1 + t2) / 2
            else:
                continue
