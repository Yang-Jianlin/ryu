import networkx as nx
import matplotlib.pyplot as plt


class NetTopology:
    def __init__(self, nodes, links):
        self.G = nx.Graph()
        self.nodes = nodes
        self.links = links

    def create_topo(self):
        self.G.add_nodes_from(self.nodes)
        self.G.add_edges_from(self.links)

    def polt_topo(self):
        nx.draw(self.G, with_labels=True, font_weight='bold')
        plt.show()


if __name__ == '__main__':
    nodes = [1, 2, 3]
    links = [[1, 2], [1, 3], [2, 3]]
    net_topo = NetTopology(nodes, links)
    net_topo.create_topo()
    net_topo.polt_topo()
