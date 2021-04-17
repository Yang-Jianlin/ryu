from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.ofproto import ofproto_v1_3
'''
通过交换hello消息建立安全通道后，执行openflow控制器和交换机的握手。
在两者握手完成后，即可对openflow交换机进行控制。
握手过程中，控制器向交换机发送问询功能的features请求消息，交换机返回features响应消息，从而完成握手。
该程序的send_feature_request()方法是控制器发送问询功能的features请求消息；
switch_features_handler()方法是交换机返回features响应消息
'''


class Switchfeature(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Switchfeature, self).__init__(*args, **kwargs)

    def send_feature_request(self, datapath):
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPFeaturesRequest(datapath)
        datapath.send_msg(req)
        print('request end')

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        print('--------------send request-------------')
        self.send_feature_request(datapath)

        print('--------------receive reply-------------')
        print('OFPSwitchFeatures received: datapath_id={0} n_buffers={1} n_tables={2} capabilities={3}'.format(msg.datapath_id, msg.n_buffers, msg.n_tables, msg.capabilities))
        print()
