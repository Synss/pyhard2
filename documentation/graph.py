import pydot
import pyhard2.driver as drv


def traverse_iface(parent_node, parent, graph):
    for child_name, child in parent.__dict__.iteritems():
        child_node = pydot.Node(name=id(child), label=child_name)
        if child_name is "_parent":
            continue
        elif isinstance(child, drv.Protocol):
            parent_node.set_fontcolor("red")
        elif isinstance(child, drv.Command):
            child_node.set_fontcolor("blue")
            graph.add_node(child_node)
            graph.add_edge(pydot.Edge(parent_node, child_node, weight=1))
        elif isinstance(child, drv.Subsystem):
            graph.add_node(child_node)
            graph.add_edge(pydot.Edge(parent_node, child_node, weight=3))
            traverse_iface(child_node, child, graph)


def generate_graph(driver_name, driver, filename):
    graph = pydot.Dot("_", graph_type="digraph", rankdir="LR")
    graph.set_node_defaults(shape="none", fontsize=10)
    traverse_iface(pydot.Node(driver_name), driver, graph)
    graph.write(filename, prog="dot")

