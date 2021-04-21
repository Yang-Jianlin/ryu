from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller import ofp_event
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
'''
自学习交换机的实现
结合了握手数据解析、流表下发、转发表学习等操作
'''


class Switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_table = {}  # mac表，即转发表，初始化为空

    # 流表的操作函数
    # 详细参见：https://blog.csdn.net/weixin_40042248/article/details/115832995?spm=1001.2014.3001.5501
    def doflow(self, datapath, command, priority, match, actions):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
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
        command = ofp.OFPFC_ADD
        match = ofp_parser.OFPMatch()
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.doflow(datapath, command, 0, match, actions)

    # 关键部分，转发表的学习，流表的下发，控制器的指令等
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        global src, dst
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        dpid = datapath.id
        # msg实际上是json格式的数据，通过解析，找出in_port
        # 可用print(msg)查看详细数据
        in_port = msg.match['in_port']
        # 接下来，主要是解析出源mac地址和目的mac地址
        pkt = packet.Packet(msg.data)
        for p in pkt.protocols:
            if p.protocol_name == 'ethernet':
                src = p.src
                dst = p.dst
                print('src:{0}  dst:{1}'.format(src, dst))

        # 字典的样式如下
        # {'dpid':{'src':in_port, 'dst':out_port}}
        self.mac_table.setdefault(dpid, {})
        # 转发表的每一项就是mac地址和端口，所以在这里不需要额外的加上dst,port的对应关系，其实返回的时候目的就是源
        self.mac_table[dpid][src] = in_port

        # 若转发表存在对应关系，就按照转发表进行；没有就需要广播得到目的ip对应的mac地址
        if dst in self.mac_table[dpid]:
            out_port = self.mac_table[dpid][dst]
        else:
            out_port = ofp.OFPP_FLOOD
        actions = [ofp_parser.OFPActionOutput(out_port)]

        # 如果执行的动作不是flood，那么此时应该依据流表项进行转发操作，所以需要添加流表到交换机
        if out_port != ofp.OFPP_FLOOD:
            match = ofp_parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            command = ofp.OFPFC_ADD
            self.doflow(datapath=datapath, command=command, priority=1,
                        match=match, actions=actions)

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
        # 控制器指导执行的命令
        out = ofp_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                      in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
