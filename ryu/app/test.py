from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.lib.packet import packet, ethernet
from ryu.topology import event
from ryu.topology.api import get_switch, get_link, get_host
from ryu.ofproto import ofproto_v1_3

import matplotlib.pyplot as plt
import networkx as nx


class MyShortestForwarding(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MyShortestForwarding, self).__init__(*args, **kwargs)

        # set data structor for topo construction
        self.network = nx.DiGraph()  # store the dj graph
        self.paths = {}  # store the shortest path
        self.topology_api_app = self

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        match = ofp_parser.OFPMatch()  # for all packet first arrive, match it successful, send it ro controller
        actions = [ofp_parser.OFPActionOutput(
            ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER
        )]

        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        inst = [ofp_parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = ofp_parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)

        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        # first get event infomation
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        in_port = msg.match['in_port']
        dpid = datapath.id

        # second get ethernet protocol message
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)

        eth_src = eth_pkt.src  # note: mac info willn`t  change in network
        eth_dst = eth_pkt.dst

        out_port = self.get_out_port(datapath, eth_src, eth_dst, in_port)
        actions = [ofp_parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = ofp_parser.OFPMatch(in_port=in_port, eth_dst=eth_dst)
            self.add_flow(datapath, 1, match, actions)

        out = ofp_parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=msg.data
        )

        datapath.send_msg(out)

    @set_ev_cls(event.EventSwitchEnter)
    def get_topology(self, ev):
        # store nodes info into the Graph
        switch_list = get_switch(self.topology_api_app)
        print('switch_list:', switch_list)
        switches = []
        for switch in switch_list:
            switches.append(switch.dp.id)
        print('switches:', switches)
        self.network.add_nodes_from(switches)

        # store links info into the Graph
        link_list = get_link(self.topology_api_app)
        print('link_list:', link_list)
        links = []
        for link in link_list:
            links.append((link.src.dpid, link.dst.dpid, {'attr_dict': {'port': link.dst.port_no}}))
        print('links', links)
        self.network.add_edges_from(links)

        for link in link_list:
            links.append((link.dst.dpid, link.src.dpid, {'attr_dict': {'port': link.dst.port_no}}))
        self.network.add_edges_from(links)

        host_list = get_host(self.topology_api_app)
        print('host_list:', host_list)

    def get_out_port(self, datapath, src, dst, in_port):
        dpid = datapath.id

        # the first :Doesn`t find src host at graph
        if src not in self.network:
            self.network.add_node(src)
            self.network.add_edge(dpid, src, attr_dict={'port': in_port})
            self.network.add_edge(src, dpid)
            self.paths.setdefault(src, {})

        # second: search the shortest path, from src to dst host
        if dst in self.network:
            if dst not in self.paths[src]:  # if not cache src to dst path,then to find it
                path = nx.shortest_path(self.network, src, dst)
                self.paths[src][dst] = path

            path = self.paths[src][dst]
            next_hop = path[path.index(dpid) + 1]
            # print("1ooooooooooooooooooo")
            # print(self.network[dpid][next_hop])
            out_port = self.network[dpid][next_hop]['attr_dict']['port']
            # print("2ooooooooooooooooooo")
            # print(out_port)

            # get path info
            # print("6666666666 find dst")
            print(path)
        else:
            out_port = datapath.ofproto.OFPP_FLOOD
            # print("8888888888 not find dst")
        return out_port
