from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.lib.dpid import str_to_dpid
from ryu.lib.packet import packet
from ryu.ofproto import ofproto_v1_3
from ryu.lib import lacplib
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER

'''
应用程序主要实现网络聚合(LACP)的功能，

'''


class NetLacp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    # 添加该应用程序运行所需要的依赖程序
    _CONTEXTS = {'lacplib': lacplib.LacpLib}

    def __init__(self, *args, **kwargs):
        super(NetLacp, self).__init__(*args, **kwargs)
        self._lacp = kwargs['lacplib']
        # 将交换机01的1、2端口绑定为一个逻辑平面
        # 若网络中存在着多个逻辑平面，多个LACP，就需要调用多次add()
        self._lacp.add(dpid=str_to_dpid('0000000000000001'), ports=[1, 2])
        self.mac_table = {}

    def add_flow(self, datapath, priority, match, actions):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        command = ofp.OFPFC_ADD
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        req = ofp_parser.OFPFlowMod(datapath=datapath, command=command,
                                    priority=priority, match=match, instructions=inst)
        datapath.send_msg(req)

    # 删除流表的方法，本应用中，在物理平面的状态改变(所属的逻辑平面变化)之后，
    # 需要将对于的流表项清除，否则达不到LACP的效果
    def del_flow(self, datapath, match):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPFlowMod(datapath=datapath,
                                    command=ofp.OFPFC_DELETE,
                                    out_port=ofp.OFPP_ANY,
                                    out_group=ofp.OFPG_ANY,
                                    match=match)
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

    # 需要对流表和流表项做一系列的操作，这里和自学习交换机的packet_in一个道理
    @set_ev_cls(lacplib.EventPacketIn, MAIN_DISPATCHER)
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
            self.add_flow(datapath=datapath, priority=1,
                          match=match, actions=actions)

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
        # 控制器指导执行的命令
        out = ofp_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                      in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    # 当交换机的状态出现变化时，就需要对流表做一些操作
    @set_ev_cls(lacplib.EventSlaveStateChanged, MAIN_DISPATCHER)
    def slave_state_changed_handler(self, ev):
        # 对于这四行解析之所以这样，不同于之前的ev.msg，
        # 可以打开lacplib.EventSlaveStateChanged中看一下初始化函数就明白了
        datapath = ev.datapath
        dpid = datapath.id
        port = ev.port
        enabled = ev.enabled
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        if dpid in self.mac_table:
            for mac in self.mac_table[dpid]:
                match = ofp_parser.OFPMatch(eth_dst=mac)
                self.del_flow(datapath=datapath, match=match)
            del self.mac_table[dpid]
        self.mac_table.setdefault(dpid, {})
