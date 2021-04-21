from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller import ofp_event
from ryu.ofproto import ofproto_v1_3
'''
流表的操作，
这个程序主要介绍了流表的添加
即，控制器向交换机下发流表
'''


class Sendflow(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def send_flow_mod(self, datapath, command, priority, match, actions):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        req = ofp_parser.OFPFlowMod(datapath=datapath, command=command,
                                    priority=priority, match=match, instructions=inst)
        datapath.send_msg(req)  # 发送流表项

    # install table-miss flow entry
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        # 关于ofp_parser和ofp之间的区别，凡是方法即加（）的都是ofp_parser
        # 凡是单个的不是方法，是变量的都是ofp
        ofp_parser = datapath.ofproto_parser
        ofp = datapath.ofproto
        print('--------------receive reply-------------')
        print('OFPSwitchFeatures received: datapath_id={0} n_buffers={1} n_tables={2} capabilities={3}'
              .format(msg.datapath_id, msg.n_buffers, msg.n_tables, msg.capabilities))
        print()

        # 这里的command表示操作流表的方式，以下之一
        # OFPFC_ADD,OFPFC_MODIFY,OFPFC_MODIFY_STRICT,OFPFC_DELETE,OFPFC_DELETE_STRICT
        flag = int(input('Please enter num to choose the way of add flow:'))
        # 添加流表，priority=1 actions=CONTROLLER:65535
        if flag == 0:
            command = ofp.OFPFC_ADD
            match = ofp_parser.OFPMatch()
            # actions=CONTROLLER:65535，ofp.OFPCML_NO_BUFFER表示设定为max_len以便接下来的封包传送
            actions = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
            self.send_flow_mod(datapath, command, 1, match, actions)
        # 添加流表，priority=1,in_port="s1-eth1" actions=ALL
        elif flag == 1:
            command = ofp.OFPFC_ADD
            # 匹配域in_port="s1-eth1"
            match = ofp_parser.OFPMatch(in_port=1)
            # actions=ALL
            actions = [ofp_parser.OFPActionOutput(ofp.OFPP_ALL)]
            self.send_flow_mod(datapath, command, 1, match, actions)
        else:
            exit()
