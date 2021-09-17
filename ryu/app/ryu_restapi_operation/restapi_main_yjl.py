from ryu.app.operate_restapi_yjl import GetInformation, PostOperation
import time


class Interface:
    def printer(self, text, delay=0.03):
        """打字机效果"""

        for ch in text:
            print(ch, end='', flush=True)
            time.sleep(delay)

    def show_face(self):
        print('<<====================<SDN NetWork Application>====================>>')
        self.printer('>^_^<>>>>>>>>>>>>>>>>>>>>>^_^<<按提示操作>>^_^<<<<<<<<<<<<<<<<<<<<>^_^<')
        print()

        home_choose = input('选择操作类型(1、查看流表 || 2、流表操作 || 3、退出):')
        while True:
            if home_choose == '3':
                exit()
            ip_port = list(input('输入ip和port:').split())
            if home_choose == '1':
                getinfo = GetInformation(ip_port[0], ip_port[1])
                getinfo.show_flow()
                home_choose = input('选择操作类型(1、查看流表 || 2、流表操作 || 3、退出):')
            elif home_choose == '2':
                postoper = PostOperation(ip_port[0], ip_port[1])
                opera_flow_choose = input('1、添加流表 || 2、删除流表 || 3、清空流表:')
                while True:
                    if opera_flow_choose == '1':
                        info = list(input('输入参数(dpid,cookie,priority,in_port,type,port):').split())
                        postoper.post_add_flow(dpid=int(info[0]), cookie=int(info[1]), priority=int(info[2]),
                                               in_port=info[3], type=info[4], port=info[5])
                        opera_flow_choose = input('1、添加流表 || 2、删除流表 || 3、清空流表 || 4、退出:')
                    elif opera_flow_choose == '2':
                        info = list(input('输入参数(dpid,cookie,priority,in_port,type,port):').split())
                        postoper.post_del_flow(dpid=int(info[0]), cookie=int(info[1]), priority=int(info[2]),
                                               in_port=int(info[3]), type=info[4], port=info[5])
                        opera_flow_choose = input('1、添加流表 || 2、删除流表 || 3、清空流表 || 4、退出:')
                    elif opera_flow_choose == '3':
                        info = input('输入dpid：')
                        postoper.post_clear_flow(dpid=info)
                        opera_flow_choose = input('1、添加流表 || 2、删除流表 || 3、清空流表 || 4、退出:')
                    elif opera_flow_choose == '4':
                        break
                    else:
                        print('！！！输入有误，请重新选择！！！')
                        opera_flow_choose = input('1、添加流表 || 2、删除流表 || 3、清空流表 || 4、退出:')
                home_choose = input('选择操作类型(1、查看流表 || 2、流表操作 || 3、退出):')
            else:
                print('！！！输入有误，请重新选择！！！')
                home_choose = input('选择操作类型(1、查看流表 || 2、流表操作 || 3、退出):')


if __name__ == '__main__':
    face = Interface()
    face.show_face()
