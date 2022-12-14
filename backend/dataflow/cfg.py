from platform import node
from backend.dataflow.basicblock import BasicBlock

"""
CFG: Control Flow Graph

nodes: sequence of basicblock
edges: sequence of edge(u,v), which represents after block u is executed, block v may be executed
links: links[u][0] represent the Prev of u, links[u][1] represent the Succ of u,
"""


class CFG:
    def __init__(self, nodes: list[BasicBlock], edges: list[(int, int)]) -> None:
        self.nodes = nodes
        self.edges = edges
        self.avaliable = [False for _ in range(len(nodes))]
        self.links = []
        for i in range(len(nodes)):
            self.links.append((set(), set()))
        for (u, v) in edges:
            self.links[u][1].add(v)
            self.links[v][0].add(u)
            # print(u, v)
        # 写一个拓扑排序判断可达性
        q = []
        q.append(0)
        head = 0
        tail = 1
        self.avaliable[0] = True
        while(head != tail):
            now_val = q[head]
            head += 1
            for x in self.links[now_val][1]:
                if self.avaliable[x] == False:
                    q.append(x)
                    tail += 1
                    self.avaliable[x] = True
    def getBlock(self, id):
        return self.nodes[id]

    def getPrev(self, id):
        return self.links[id][0]

    def getSucc(self, id):
        return self.links[id][1]

    def getInDegree(self, id):
        return len(self.links[id][0])

    def getOutDegree(self, id):
        return len(self.links[id][1])

    def iterator(self):
        return iter(self.nodes)

    def judge(self, id: int):
        return self.avaliable[id]