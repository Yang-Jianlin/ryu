from ryu.controller import ofp_event
from ryu.lib import hub
from ryu.lib.dpid import str_to_dpid
from ryu.base import app_manager
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls


class SimpleMonitor13(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        # 用于存储交换机对象
        self.datapaths = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        if datapath.id not in self.datapaths:
            self.datapaths[datapath.id] = datapath

        hub.spawn(self.rr_link_change)

    def rr_link_change(self):
        # flag用于标记每一段时间间隔的流表项下发规则
        # 例如flag=1表示走上面一条链路，flag=2表示走下面一条链路
        flag = 1

        # 一致循环的执行流表项的清除添加工作
        while True:
            print('datapath:', self.datapaths)
            try:
                if flag == 1:
                    print('flag:', flag)
                    flag = 2
                    # 添加流表项之前先删除交换机s1，s2中存在的流表项
                    self.match_flow(dpid=1, in_port=1, out_port=1, priority=1, add_del=0)
                    self.match_flow(dpid=2, in_port=1, out_port=1, priority=1, add_del=0)

                    # 向交换机s1中添加流表项
                    self.match_flow(dpid=1, in_port=1, out_port=2, priority=1, add_del=1)
                    self.match_flow(dpid=1, in_port=2, out_port=1, priority=1, add_del=1)

                    # 向交换机s2中添加流表项
                    self.match_flow(dpid=2, in_port=1, out_port=2, priority=1, add_del=1)
                    self.match_flow(dpid=2, in_port=2, out_port=1, priority=1, add_del=1)
                elif flag == 2:
                    print('flag:', flag)
                    flag = 1
                    self.match_flow(dpid=1, in_port=1, out_port=1, priority=1, add_del=0)
                    self.match_flow(dpid=2, in_port=1, out_port=1, priority=1, add_del=0)

                    self.match_flow(dpid=1, in_port=1, out_port=3, priority=1, add_del=1)
                    self.match_flow(dpid=1, in_port=3, out_port=1, priority=1, add_del=1)

                    self.match_flow(dpid=2, in_port=1, out_port=3, priority=1, add_del=1)
                    self.match_flow(dpid=2, in_port=3, out_port=1, priority=1, add_del=1)

            except Exception as info:
                print('info:', info)

            hub.sleep(10) # 间隔10秒切换一次

    def match_flow(self, dpid, in_port, out_port, priority, add_del):
        ofp_parser = self.datapaths[dpid].ofproto_parser
        ofp = self.datapaths[dpid].ofproto
        actions = [ofp_parser.OFPActionOutput(out_port)]
        # add_del变量用来判断是该执行删除还是添加操作，如果是1则执行添加，如果为0执行删除
        if add_del == 1:
            match = ofp_parser.OFPMatch(in_port=in_port)
            self.add_flow(datapath=self.datapaths[dpid], priority=priority, match=match, actions=actions)
        if add_del == 0:
            match = ofp_parser.OFPMatch()
            self.del_flow(datapath=self.datapaths[dpid], match=match)

    # 删除流表项的方法，方法直接清除交换机的所有流表项
    def del_flow(self, datapath, match):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPFlowMod(datapath=datapath,
                                    command=ofp.OFPFC_DELETE,
                                    out_port=ofp.OFPP_ANY,
                                    out_group=ofp.OFPG_ANY,
                                    match=match)
        datapath.send_msg(req)

    # 添加流表项的方法
    def add_flow(self, datapath, priority, match, actions):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        command = ofp.OFPFC_ADD
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        req = ofp_parser.OFPFlowMod(datapath=datapath, command=command,
                                    priority=priority, match=match, instructions=inst)
        datapath.send_msg(req)
