mac_table = {}
dpid = input('enter dpid:')

mac_table.setdefault(dpid, {})
print(mac_table)

src = input('enter src:')
dst = input('enter dst:')
inport = input('enter inport:')
mac_table[dpid][src] = inport
mac_table[dpid][dst] = inport
print(mac_table)

print(mac_table[dpid])
for i in mac_table[dpid]:
    print(i)
for j in mac_table[dpid].values():
    print(j)
