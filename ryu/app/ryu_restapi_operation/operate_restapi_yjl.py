import requests
import time
import re


class GetInformation:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def get_switch_id(self):
        url = 'http://' + self.ip + ':' + self.port + '/stats/switches'
        re_switch_id = requests.get(url=url).json()
        switch_id_hex = []
        for i in re_switch_id:
            switch_id_hex.append(hex(i))

        return switch_id_hex

    def get_flow_table(self):
        url = 'http://' + self.ip + ':' + self.port + '/stats/flow/%d'
        list_switch = self.get_switch_id()
        all_flow = []
        for switch in list_switch:
            new_url = format(url % int(switch, 16))
            re_switch_flow = requests.get(url=new_url).json()
            all_flow.append(re_switch_flow)

        return all_flow

    def show_flow(self):
        list_flow = self.get_flow_table()
        for flow in list_flow:
            for dpid in flow.keys():
                dp_id = dpid
                print('switch_id:{0}({1})'.format(hex(int(dp_id)), int(dp_id)))
            for list_table in flow.values():
                for table in list_table:
                    print(table)


class PostOperation:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def post_add_flow(self, dpid=None, cookie=0, priority=0, in_port=1, type='OUTPUT', port='CONTROLLER'):
        url = 'http://' + self.ip + ':' + self.port + '/stats/flowentry/add'
        if in_port == 'None':
            # 添加的默认流表项数据信息
            data = {
                "dpid": dpid,
                "cookie": cookie,
                "cookie_mask": 0,
                "table_id": 0,
                "priority": priority,
                "flags": 0,
                "actions": [
                    {
                        "type": type,
                        "port": port
                    }
                ]
            }
        else:
            in_port = int(in_port)
            data = {
                "dpid": dpid,
                "cookie": cookie,
                "cookie_mask": 0,
                "table_id": 0,
                "priority": priority,
                "flags": 0,
                "match": {
                    "in_port": in_port
                },
                "actions": [
                    {
                        "type": type,
                        "port": port
                    }
                ]
            }

        response = requests.post(url=url, json=data)
        if response.status_code == 200:
            print('Successfully Add!')
        else:
            print('Fail!')

    def post_del_flow(self, dpid=None, cookie=0, priority=0, in_port=1, type='OUTPUT', port='CONTROLLER'):
        url = url = 'http://' + self.ip + ':' + self.port + '/stats/flowentry/delete_strict'
        data = {
            "dpid": dpid,
            "cookie": cookie,
            "cookie_mask": 1,
            "table_id": 0,
            "priority": priority,
            "flags": 1,
            "match": {
                "in_port": in_port,
            },
            "actions": [
                {
                    "type": type,
                    "port": port
                }
            ]
        }

        response = requests.post(url=url, json=data)
        if response.status_code == 200:
            print('Successfully Delete!')
        else:
            print('Fail!')

    def post_clear_flow(self, dpid=None):
        url = 'http://' + self.ip + ':' + self.port + '/stats/flowentry/clear/' + str(dpid)
        response = requests.delete(url=url)
        if response.status_code == 200:
            print('Successfully Clear!')
        else:
            print('Fail!')
