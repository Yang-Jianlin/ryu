import networkx as nx
import matplotlib.pyplot as plt


class NetTopology:
    def __init__(self, nodes, links):
        # 创建一个空图
        self.G = nx.Graph()
        # 图中包含节点和边
        self.nodes = nodes
        self.links = links

    # 将节点列表和边列表添加到图中
    def create_topo(self):
        self.G.add_nodes_from(self.nodes)
        self.G.add_edges_from(self.links)

    # 绘图方法，可以将构建的图打印出来
    def polt_topo(self):
        nx.draw(self.G, with_labels=True, font_weight='bold')
        plt.show()

    # 按照最短路径找出源到目的的路径，并给出下一条的输出端口
    def shortest(self, datapath, src, tar):
        # path是源到目的的路径，比如1-5，会输出[1, 4, 5]
        path = nx.shortest_path(self.G, src, tar)
        # 下一跳，也就是1-5，从1开始的下一跳是4，datapath代表当前的节点的id，比如1代码1节点的id，1节点的下一跳就是4
        next_hop = path[path.index(datapath) + 1]
        # out_port是指到下一跳需要经过哪个端口转发出去，比如下一条是4，经过5端口转发出去
        out_port = self.G[datapath][next_hop]['att_dict']['port']

        print(path)
        print(out_port)


if __name__ == '__main__':
    nodes = [1, 2, 3, 4, 5]
    links = [(1, 2, {'att_dict': {'port': 1}}), (2, 3, {'att_dict': {'port': 3}}),
             (3, 5, {'att_dict': {'port': 4}}), (1, 4, {'att_dict': {'port': 5}}),
             (4, 5, {'att_dict': {'port': 6}})]
    net_topo = NetTopology(nodes, links)
    net_topo.create_topo()
    net_topo.polt_topo()
    net_topo.shortest(1, 1, 5)
