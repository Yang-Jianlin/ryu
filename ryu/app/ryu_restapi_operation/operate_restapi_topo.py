#!/usr/bin/env python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call

def myNetwork():

    net = Mininet( topo=None,
                   build=False,
                   ipBase='10.0.0.0/8')

    info( '*** Adding controller\n' )
    as1-c1=net.addController(name='as1-c1',
                      controller=RemoteController,
                      ip='172.17.0.2',
                      protocol='tcp',
                      port=6633)

    as2-c1=net.addController(name='as2-c1',
                      controller=RemoteController,
                      ip='172.17.0.3',
                      protocol='tcp',
                      port=6633)

    info( '*** Add switches\n')
    as1-s1 = net.addSwitch('as1-s1', cls=OVSKernelSwitch, dpid='0000000000000011')
    as1-s2 = net.addSwitch('as1-s2', cls=OVSKernelSwitch, dpid='0000000000000012')
    as2-s1 = net.addSwitch('as2-s1', cls=OVSKernelSwitch, dpid='0000000000000021')
    r4 = net.addHost('r4', cls=Node, ip='0.0.0.0')
    r4.cmd('sysctl -w net.ipv4.ip_forward=1')
    r5 = net.addHost('r5', cls=Node, ip='0.0.0.0')
    r5.cmd('sysctl -w net.ipv4.ip_forward=1')

    info( '*** Add hosts\n')
    as1-h1 = net.addHost('as1-h1', cls=Host, ip='10.0.1.1/24', defaultRoute=None)
    as1-h2 = net.addHost('as1-h2', cls=Host, ip='10.0.1.2/24', defaultRoute=None)
    as1-h3 = net.addHost('as1-h3', cls=Host, ip='10.0.1.3/24', defaultRoute=None)
    as2-h1 = net.addHost('as2-h1', cls=Host, ip='10.0.2.1/24', defaultRoute=None)
    as2-h2 = net.addHost('as2-h2', cls=Host, ip='10.0.2.2/24', defaultRoute=None)

    info( '*** Add links\n')
    net.addLink(as1-h1, as1-s1)
    net.addLink(as1-s1, as1-h2)
    net.addLink(as1-h3, as1-s2)
    net.addLink(as2-h1, as2-s1)
    net.addLink(as2-s1, as2-h2)
    net.addLink(as1-s1, as1-s2)
    net.addLink(as1-s1, r4)
    net.addLink(r4, as1-s2)
    net.addLink(as2-s1, r5)
    net.addLink(r4, r5)

    info( '*** Starting network\n')
    net.build()
    info( '*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info( '*** Starting switches\n')
    net.get('as1-s1').start([as1-c1])
    net.get('as1-s2').start([as1-c1])
    net.get('as2-s1').start([as2-c1])

    info( '*** Post configure switches and hosts\n')

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()
