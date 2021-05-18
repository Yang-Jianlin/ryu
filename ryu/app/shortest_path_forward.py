from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.topology.api import get_switch, get_link
from ryu.topology import event
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet

import networkx as nx


class PathForward(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PathForward, self).__init__(*args, **kwargs)
        self.G = nx.DiGraph()
        # 作为get_switch()和get_link()方法的参数传入
        self.topology_api_app = self

    # 添加流表项的方法
    def add_flow(self, datapath, priority, match, actions):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        command = ofp.OFPFC_ADD
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        req = ofp_parser.OFPFlowMod(datapath=datapath, command=command,
                                    priority=priority, match=match, instructions=inst)
        datapath.send_msg(req)

    # 当控制器和交换机开始的握手动作完成后，进行table-miss(默认流表)的添加
    # 关于这一段代码的详细解析，参见：https://blog.csdn.net/weixin_40042248/article/details/115749340
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

    @set_ev_cls(event.EventSwitchEnter)
    def get_topo(self, ev):
        switch_list = get_switch(self.topology_api_app)
        switches = []
        # 得到每个设备的id，并写入图中作为图的节点
        for switch in switch_list:
            switches.append(switch.dp.id)
        self.G.add_nodes_from(switches)

        link_list = get_link(self.topology_api_app)
        links = []
        # 将得到的链路的信息作为边写入图中
        for link in link_list:
            links.append((link.src.dpid, link.dst.dpid, {'attr_dict': {'port': link.src.port_no}}))
        self.G.add_edges_from(links)

        for link in link_list:
            links.append((link.dst.dpid, link.src.dpid, {'attr_dict': {'port': link.dst.port_no}}))
        self.G.add_edges_from(links)

    def get_out_port(self, datapath, src, dst, in_port):
        dpid = datapath.id

        # 开始时，各个主机可能在图中不存在，因为开始ryu只获取了交换机的dpid，并不知道各主机的信息，
        # 所以需要将主机存入图中
        if src not in self.G:
            self.G.add_node(src)
            self.G.add_edge(dpid, src, attr_dict={'port': in_port})
            self.G.add_edge(src, dpid)

        if dst in self.G:
            path = nx.shortest_path(self.G, src, dst)
            next_hop = path[path.index(dpid) + 1]
            out_port = self.G[dpid][next_hop]['attr_dict']['port']
            print(path)
        else:
            out_port = datapath.ofproto.OFPP_FLOOD
        return out_port

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

        out_port = self.get_out_port(datapath, src, dst, in_port)
        actions = [ofp_parser.OFPActionOutput(out_port)]

        # 如果执行的动作不是flood，那么此时应该依据流表项进行转发操作，所以需要添加流表到交换机
        if out_port != ofp.OFPP_FLOOD:
            match = ofp_parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.add_flow(datapath=datapath, priority=1, match=match, actions=actions)

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
        # 控制器指导执行的命令
        out = ofp_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                      in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
