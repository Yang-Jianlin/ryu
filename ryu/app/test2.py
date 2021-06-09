lldp_delay = {'2-2-1': 0.001077413558959961, '2-3-3': 0.0016210079193115234,
              '1-2-2': 0.0015943050384521484, '3-2-2': 0.0012526512145996094}

switch_delay = {1: 0.0009899139404296875,
                3: 0.0012354850769042969,
                2: 0.001295328140258789}

links_src_dst = [[2, 3, 0], [2, 1, 0],
                 [1, 2, 0], [3, 2, 0],
                 [3, 2, 0], [1, 2, 0],
                 [2, 1, 0], [2, 3, 0]]

link_delay = {}
for key in lldp_delay:
    list = key.split('-')
    l = (int(list[0]), int(list[2]))
    num = 0
    for i in links_src_dst:
        num += 1
        if l == (i[0], i[1]):
            i[2] = lldp_delay[key]

print(links_src_dst)



