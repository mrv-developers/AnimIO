__author__ = "\n".join(['Aric Hagberg (hagberg@lanl.gov)',
						'Pieter Swart (swart@lanl.gov)',
						'Dan Schult(dschult@colgate.edu)'])
#    Copyright (C) 2004-2009 by 
#    Aric Hagberg <hagberg@lanl.gov>
#    Dan Schult <dschult@colgate.edu>
#    Pieter Swart <swart@lanl.gov>
#    All rights reserved.
#    BSD license.
#
__docformat__ = "restructuredtext en"

from networkx.exception import NetworkXException, NetworkXError
from copy import deepcopy

class Graph(object):
    def __init__(self, data=None, name='', **attr):
        self.graph = {}   # dictionary for graph attributes
        self.node = {}    # empty node dict (created before convert)
        self.adj = {}     # empty adjacency dict
        # load graph attributes (must be after convert)
        self.graph.update(attr)
        self.name = name
        self.edge = self.adj

    def __str__(self):
        return self.name

    def __iter__(self):
        return self.adj.iterkeys()

    def __contains__(self,n):
        try:
            return n in self.adj
        except TypeError:
            return False
        
    def __len__(self):
        return len(self.adj)

    def __getitem__(self, n):
        return self.adj[n]
    

    def add_node(self, n, attr_dict=None, **attr):
        # set up attribute dict
        if attr_dict is None:
            attr_dict=attr
        else:
            try:
                attr_dict.update(attr)
            except AttributeError:
                raise NetworkXError(\
                    "The attr_dict argument must be a dictionary.")
        if n not in self.adj:
            self.adj[n] = {}
            self.node[n] = attr_dict
        else: # update attr even if node already exists            
            self.node[n].update(attr_dict)


    def add_nodes_from(self, nodes, **attr):
        for n in nodes:
            if n not in self.adj:
                self.adj[n] = {}
                self.node[n] = attr.copy()
            else:
                self.node[n].update(attr)

    def remove_node(self,n):
        
        adj = self.adj
        try:
            nbrs = adj[n].keys() # keys handles self-loops (allow mutation later)
            del self.node[n]
        except KeyError: # NetworkXError if n not in self
            raise NetworkXError("The node %s is not in the graph."%(n,))
        for u in nbrs:  
            del adj[u][n]   # remove all edges n-u in graph
        del adj[n]          # now remove node


    def remove_nodes_from(self, nodes):
        
        adj = self.adj
        for n in nodes:
            try: 
                del self.node[n]
                for u in adj[n].keys():   # keys() handles self-loops 
                    del adj[u][n]         #(allows mutation of dict in loop)
                del adj[n]
            except KeyError:
                pass


    def nodes_iter(self, data=False):
        
        if data:
            return self.node.iteritems()
        return self.adj.iterkeys()

    def nodes(self, data=False):
        
        return list(self.nodes_iter(data=data))

    def number_of_nodes(self):
        
        return len(self.adj)

    def order(self):
        
        return len(self.adj)

    def has_node(self, n):
        
        try:
            return n in self.adj
        except TypeError:
            return False

    def add_edge(self, u, v, attr_dict=None, **attr):  
        
        # set up attribute dictionary
        if attr_dict is None:
            attr_dict=attr
        else:
            try:
                attr_dict.update(attr)
            except AttributeError:
                raise NetworkXError(\
                    "The attr_dict argument must be a dictionary.")
        # add nodes            
        if u not in self.adj: 
            self.adj[u] = {}
            self.node[u] = {}
        if v not in self.adj: 
            self.adj[v] = {}
            self.node[v] = {}
        # add the edge
        datadict=self.adj[u].get(v,{})
        datadict.update(attr_dict)
        self.adj[u][v] = datadict
        self.adj[v][u] = datadict


    def add_edges_from(self, ebunch, attr_dict=None, **attr):  
        
        # set up attribute dict
        if attr_dict is None:
            attr_dict=attr
        else:
            try:
                attr_dict.update(attr)
            except AttributeError:
                raise NetworkXError(\
                    "The attr_dict argument must be a dictionary.")
        # process ebunch
        for e in ebunch:
            ne=len(e)
            if ne==3:
                u,v,dd = e
            elif ne==2:
                u,v = e  
                dd = {}
            else: 
                raise NetworkXError(\
                    "Edge tuple %s must be a 2-tuple or 3-tuple."%(e,))
            if u not in self.adj: 
                self.adj[u] = {}
                self.node[u] = {}
            if v not in self.adj: 
                self.adj[v] = {}
                self.node[v] = {}
            datadict=self.adj[u].get(v,{})
            datadict.update(attr_dict) 
            datadict.update(dd)
            self.adj[u][v] = datadict
            self.adj[v][u] = datadict


    def add_weighted_edges_from(self, ebunch, **attr):  
        
        self.add_edges_from(((u,v,{'weight':d}) for u,v,d in ebunch),**attr)

    def remove_edge(self, u, v): 
        
        try:
            del self.adj[u][v]   
            if u != v:  # self-loop needs only one entry removed
                del self.adj[v][u]   
        except KeyError: 
            raise NetworkXError("The edge %s-%s is not in the graph"%(u,v))



    def remove_edges_from(self, ebunch): 
        
        for e in ebunch:
            u,v = e[:2]  # ignore edge data if present
            if u in self.adj and v in self.adj[u]:
                del self.adj[u][v]   
                if u != v:  # self loop needs only one entry removed
                    del self.adj[v][u]   


    def has_edge(self, u, v):
        
        try:
            return v in self.adj[u]
        except KeyError:
            return False


    def neighbors(self, n):
        
        try:
            return self.adj[n].keys()
        except KeyError:
            raise NetworkXError("The node %s is not in the graph."%(n,))

    def neighbors_iter(self, n):
        
        try:
            return self.adj[n].iterkeys()
        except KeyError:
            raise NetworkXError("The node %s is not in the graph."%(n,))

    def edges(self, nbunch=None, data=False):
        
        return list(self.edges_iter(nbunch, data))

    def edges_iter(self, nbunch=None, data=False):
        
        seen={}     # helper dict to keep track of multiply stored edges
        if nbunch is None:
            nodes_nbrs = self.adj.iteritems()
        else:
            nodes_nbrs=((n,self.adj[n]) for n in self.nbunch_iter(nbunch))
        if data:
            for n,nbrs in nodes_nbrs:
                for nbr,data in nbrs.iteritems():
                    if nbr not in seen:
                        yield (n,nbr,data)
                seen[n]=1
        else:
            for n,nbrs in nodes_nbrs:
                for nbr in nbrs:
                    if nbr not in seen:
                        yield (n,nbr)
                seen[n] = 1
        del seen


    def get_edge_data(self, u, v, default=None):
        
        try:
            return self.adj[u][v]
        except KeyError:
            return default

    def adjacency_list(self):
        
        return map(list,self.adj.itervalues())
        
    def adjacency_iter(self):
        
        return self.adj.iteritems()

    def degree(self, nbunch=None, with_labels=False, weighted=False):
        
        if with_labels:           # return a dict
            return dict(self.degree_iter(nbunch,weighted=weighted))
        elif nbunch in self:      # return a single node
            return self.degree_iter(nbunch,weighted=weighted).next()[1]
        else:                     # return a list
            return [d for (n,d) in self.degree_iter(nbunch,weighted=weighted)]

    def degree_iter(self, nbunch=None, weighted=False):
        
        if nbunch is None:
            nodes_nbrs = self.adj.iteritems()
        else:
            nodes_nbrs=((n,self.adj[n]) for n in self.nbunch_iter(nbunch))
  
        if weighted:                        
        # edge weighted graph - degree is sum of nbr edge weights
            for n,nbrs in nodes_nbrs:
                yield (n, sum((nbrs[nbr].get('weight',1) for nbr in nbrs)) +
                              (n in nbrs and nbrs[n].get('weight',1)))
        else:
            for n,nbrs in nodes_nbrs:
                yield (n,len(nbrs)+(n in nbrs)) # return tuple (n,degree)


    def clear(self):
        
        self.name = ''
        self.adj.clear() 
        self.node.clear()
        self.graph.clear()

    def copy(self):
        
        return deepcopy(self)

    def is_multigraph(self):
        
        return False


    def is_directed(self):
        
        return False

    def to_directed(self):
        
        from networkx import DiGraph 
        G=DiGraph()
        G.name=self.name
        G.add_nodes_from(self)
        G.add_edges_from( ((u,v,deepcopy(data)) 
                           for u,nbrs in self.adjacency_iter() 
                           for v,data in nbrs.iteritems()) )
        G.graph=deepcopy(self.graph)
        G.node=deepcopy(self.node)
        return G

    def to_undirected(self):
        
        return deepcopy(self)

    def subgraph(self, nbunch):
        
        bunch =self.nbunch_iter(nbunch)
        # create new graph and copy subgraph into it       
        H = self.__class__()
        H.name = "Subgraph of (%s)"%(self.name)
        # namespace shortcuts for speed
        H_adj=H.adj
        self_adj=self.adj
        # add nodes and edges (undirected method)
        for n in bunch:
            Hnbrs={}
            H_adj[n]=Hnbrs
            for nbr,d in self_adj[n].iteritems():
                if nbr in H_adj:
                    # add both representations of edge: n-nbr and nbr-n
                    Hnbrs[nbr]=d
                    H_adj[nbr][n]=d
        # copy node and attribute dictionaries
        H.node=self.node.copy()
        H.graph=self.graph.copy()
        return H


    def nodes_with_selfloops(self):
        
        return [ n for n,nbrs in self.adj.iteritems() if n in nbrs ]

    def selfloop_edges(self, data=False):
        
        if data:
            return [ (n,n,nbrs[n]) 
                     for n,nbrs in self.adj.iteritems() if n in nbrs ]
        else:
            return [ (n,n) 
                     for n,nbrs in self.adj.iteritems() if n in nbrs ]


    def number_of_selfloops(self):
        
        return len(self.selfloop_edges())


    def size(self, weighted=False):
        

        return sum(self.degree(weighted=weighted))/2

    def number_of_edges(self, u=None, v=None):
        
        if u is None: return self.size()
        if v in self.adj[u]:
            return 1
        else:
            return 0


    def add_star(self, nlist, **attr):
        
        v=nlist[0]
        edges=((v,n) for n in nlist[1:])
        self.add_edges_from(edges, **attr)

    def add_path(self, nlist, **attr):
        
        edges=zip(nlist[:-1],nlist[1:])
        self.add_edges_from(edges, **attr)

    def add_cycle(self, nlist, **attr):
        
        edges=zip(nlist,nlist[1:]+[nlist[0]])
        self.add_edges_from(edges, **attr)


    def nbunch_iter(self, nbunch=None):
        
        if nbunch is None:   # include all nodes via iterator
            bunch=self.adj.iterkeys()
        elif nbunch in self: # if nbunch is a single node 
            bunch=[nbunch].__iter__()
        else:                # if nbunch is a sequence of nodes
            def bunch_iter(nlist,adj):
                try:    
                    for n in nlist:
                        if n in adj:
                            yield n
                except TypeError,e:
                    message=e.args[0]
                    print message
                    # capture error for non-sequence/iterator nbunch.
                    if 'iterable' in message:  
                        raise NetworkXError(
                            "nbunch is not a node or a sequence of nodes.")
                    # capture error for unhashable node.
                    elif 'hashable' in message: 
                        raise NetworkXError(
                            "Node %s in the sequence nbunch is not a valid node."%n)
                    else: raise
            bunch=bunch_iter(nbunch,self.adj)
        return bunch
