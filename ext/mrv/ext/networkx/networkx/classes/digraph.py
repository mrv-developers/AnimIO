
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

from networkx.classes.graph import Graph
from networkx.exception import NetworkXException, NetworkXError
from copy import deepcopy

class DiGraph(Graph):
    
    def __init__(self, data=None, name='', **attr):
        
        self.graph = {} # dictionary for graph attributes
        self.node = {} # dictionary for node attributes
        # We store two adjacency lists:
        # the  predecessors of node n are stored in the dict self.pred
        # the successors of node n are stored in the dict self.succ=self.adj
        self.adj = {}  # empty adjacency dictionary
        self.pred = {}  # predecessor
        self.succ = self.adj  # successor

        # load graph attributes (must be after convert)
        self.graph.update(attr)

        self.name=name
        self.edge=self.adj

        
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
        if n not in self.succ:
            self.succ[n] = {}
            self.pred[n] = {}
            self.node[n] = attr_dict
        else: # update attr even if node already exists            
            self.node[n].update(attr_dict)

    def add_nodes_from(self, nodes, **attr):
        
        for n in nodes:
            if n not in self.succ:
                self.succ[n] = {}
                self.pred[n] = {}
                self.node[n] = attr
            else: # update attr even if node already exists            
                self.node[n].update(attr)


    def remove_node(self, n):
        
        try:
            nbrs=self.succ[n]
            del self.node[n]
        except KeyError: # NetworkXError if n not in self
            raise NetworkXError("The node %s is not in the digraph."%(n,))
        for u in nbrs:
            del self.pred[u][n] # remove all edges n-u in digraph
        del self.succ[n]          # remove node from succ
        for u in self.pred[n]:  
            del self.succ[u][n] # remove all edges n-u in digraph
        del self.pred[n]          # remove node from pred


    def remove_nodes_from(self, nbunch):
        
        for n in nbunch: 
            try:
                succs=self.succ[n]
                del self.node[n]
                for u in succs:  
                    del self.pred[u][n] # remove all edges n-u in digraph
                del self.succ[n]          # now remove node
                for u in self.pred[n]:  
                    del self.succ[u][n] # remove all edges n-u in digraph
                del self.pred[n]          # now remove node
            except KeyError:
                pass # silent failure on remove


    def add_edge(self, u, v, attr_dict=None, **attr):  
        
        # set up attribute dict
        if attr_dict is None:
            attr_dict=attr
        else:
            try:
                attr_dict.update(attr)
            except AttributeError:
                raise NetworkXError(\
                    "The attr_dict argument must be a dictionary.")
        # add nodes            
        if u not in self.succ: 
            self.succ[u]={}
            self.pred[u]={}
            self.node[u] = {}
        if v not in self.succ: 
            self.succ[v]={}
            self.pred[v]={}
            self.node[v] = {}
        # add the edge
        datadict=self.adj[u].get(v,{})
        datadict.update(attr_dict)
        self.succ[u][v]=datadict
        self.pred[v][u]=datadict

    def add_edges_from(self, ebunch, attr_dict=None, **attr):  
        
        # set up attribute dict
        if attr_dict is None:
            attr_dict=attr
        else:
            try:
                attr_dict.update(attr)
            except AttributeError:
                raise NetworkXError(\
                    "The attr_dict argument must be a dict.")
        # process ebunch
        for e in ebunch:
            ne = len(e)
            if ne==3:
                u,v,dd = e
                assert hasattr(dd,"update")
            elif ne==2:
                u,v = e
                dd = {}
            else: 
                raise NetworkXError(\
                    "Edge tuple %s must be a 2-tuple or 3-tuple."%(e,))
            if u not in self.succ: 
                self.succ[u] = {}
                self.pred[u] = {}
                self.node[u] = {}
            if v not in self.succ: 
                self.succ[v] = {}
                self.pred[v] = {}
                self.node[v] = {}
            datadict=self.adj[u].get(v,{})
            datadict.update(attr_dict) 
            datadict.update(dd)
            self.succ[u][v] = datadict
            self.pred[v][u] = datadict


    def remove_edge(self, u, v):
        
        try:
            del self.succ[u][v]   
            del self.pred[v][u]   
        except KeyError: 
            raise NetworkXError("The edge %s-%s not in graph."%(u,v))


    def remove_edges_from(self, ebunch): 
        
        for e in ebunch:
            (u,v)=e[:2]  # ignore edge data
            if u in self.succ and v in self.succ[u]:
                del self.succ[u][v]   
                del self.pred[v][u]        


    def has_successor(self, u, v):
        
        return (u in self.succ and v in self.succ[u])

    def has_predecessor(self, u, v):
        
        return (u in self.pred and v in self.pred[u])    

    def successors_iter(self,n):
        
        try:
            return self.succ[n].iterkeys()
        except KeyError:
            raise NetworkXError("The node %s is not in the digraph."%(n,))

    def predecessors_iter(self,n):
        
        try:
            return self.pred[n].iterkeys()
        except KeyError:
            raise NetworkXError("The node %s is not in the digraph."%(n,))

    def successors(self, n):
        
        return list(self.successors_iter(n))

    def predecessors(self, n):
        
        return list(self.predecessors_iter(n))


    # digraph definitions 
    neighbors = successors
    neighbors_iter = successors_iter

    def edges_iter(self, nbunch=None, data=False):
        
        if nbunch is None:
            nodes_nbrs=self.adj.iteritems()
        else:
            nodes_nbrs=((n,self.adj[n]) for n in self.nbunch_iter(nbunch))
        if data:
            for n,nbrs in nodes_nbrs:
                for nbr,data in nbrs.iteritems():
                    yield (n,nbr,data)
        else:
            for n,nbrs in nodes_nbrs:
                for nbr in nbrs:
                    yield (n,nbr)

    # alias out_edges to edges
    out_edges_iter=edges_iter
    out_edges=Graph.edges

    def in_edges_iter(self, nbunch=None, data=False):
        
        if nbunch is None:
            nodes_nbrs=self.pred.iteritems()
        else:
            nodes_nbrs=((n,self.pred[n]) for n in self.nbunch_iter(nbunch))
        if data:
            for n,nbrs in nodes_nbrs:
                for nbr,data in nbrs.iteritems():
                    yield (nbr,n,data)
        else:
            for n,nbrs in nodes_nbrs:
                for nbr in nbrs:
                    yield (nbr,n)

    def in_edges(self, nbunch=None, data=False):
        
        return list(self.in_edges_iter(nbunch, data))

    def degree_iter(self, nbunch=None, weighted=False):
        
        from itertools import izip
        if nbunch is None:
            nodes_nbrs=izip(self.succ.iteritems(),self.pred.iteritems())
        else:
            nodes_nbrs=izip(
                ((n,self.succ[n]) for n in self.nbunch_iter(nbunch)),
                ((n,self.pred[n]) for n in self.nbunch_iter(nbunch)))

        if weighted:                        
        # edge weighted graph - degree is sum of edge weights
            for (n,succ),(n2,pred) in nodes_nbrs:
               yield (n, 
                      sum((succ[nbr].get('weight',1) for nbr in succ))+
                      sum((pred[nbr].get('weight',1) for nbr in pred)))
        else:
            for (n,succ),(n2,pred) in nodes_nbrs:
                yield (n,len(succ)+len(pred)) 

    def in_degree_iter(self, nbunch=None, weighted=False):
        
        if nbunch is None:
            nodes_nbrs=self.pred.iteritems()
        else:
            nodes_nbrs=((n,self.pred[n]) for n in self.nbunch_iter(nbunch))
  
        if weighted:                        
        # edge weighted graph - degree is sum of edge weights
            for n,nbrs in nodes_nbrs:
                yield (n, sum((nbrs[nbr].get('weight',1) for nbr in nbrs)))
        else:
            for n,nbrs in nodes_nbrs:
                yield (n,len(nbrs))


    def out_degree_iter(self, nbunch=None, weighted=False):
        
        if nbunch is None:
            nodes_nbrs=self.succ.iteritems()
        else:
            nodes_nbrs=((n,self.succ[n]) for n in self.nbunch_iter(nbunch))
  
        if weighted:                        
        # edge weighted graph - degree is sum of edge weights
            for n,nbrs in nodes_nbrs:
                yield (n, sum((nbrs[nbr].get('weight',1) for nbr in nbrs)))
        else:
            for n,nbrs in nodes_nbrs:
                yield (n,len(nbrs))


    def in_degree(self, nbunch=None, with_labels=False, weighted=False):
        
        if with_labels:           # return a dict
            return dict(self.in_degree_iter(nbunch,weighted=weighted))
        elif nbunch in self:      # return a single node
            return self.in_degree_iter(nbunch,weighted=weighted).next()[1]
        else:                     # return a list
            return [d
                    for (n,d) in self.in_degree_iter(nbunch,weighted=weighted)]


    def out_degree(self, nbunch=None, with_labels=False, weighted=False):
        
        if with_labels:           # return a dict
            return dict(self.out_degree_iter(nbunch,weighted=weighted))
        elif nbunch in self:      # return a single node
            return self.out_degree_iter(nbunch,weighted=weighted).next()[1]
        else:                     # return a list
            return [d for
                    (n,d) in self.out_degree_iter(nbunch,weighted=weighted)]

    def clear(self):
        
        self.name=''
        self.succ.clear() 
        self.pred.clear() 
        self.node.clear()
        self.graph.clear()


    def is_multigraph(self):
        
        return False


    def is_directed(self):
        
        return True

    def to_directed(self):
        
        return deepcopy(self)

    def to_undirected(self):
        
        H=Graph()
        H.name=self.name
        H.add_nodes_from(self)
        H.add_edges_from( (u,v,deepcopy(d)) 
                          for u,nbrs in self.adjacency_iter()
                          for v,d in nbrs.iteritems() )
        H.graph=deepcopy(self.graph)
        H.node=deepcopy(self.node)
        return H
    

    def reverse(self, copy=True):
        
        if copy:
            H = self.__class__(name="Reverse of (%s)"%self.name)
            H.pred=self.succ.copy()
            H.adj=self.pred.copy()
            H.succ=H.adj
            H.graph=self.graph.copy()
            H.node=self.node.copy()
        else:
            self.pred,self.succ=self.succ,self.pred
            self.adj=self.succ
            H=self
        return H


    def subgraph(self, nbunch, copy=True):
        
        bunch = self.nbunch_iter(nbunch)
        # create new graph and copy subgraph into it       
        H = self.__class__()
        H.name = "Subgraph of (%s)"%(self.name)
        # namespace shortcuts for speed
        H_succ=H.succ
        H_pred=H.pred
        self_succ=self.succ
        self_pred=self.pred
        # add nodes
        for n in bunch:
            H_succ[n]={}
            H_pred[n]={}
        # add edges
        for u in H_succ:
            Hnbrs=H_succ[u]
            for v,datadict in self_succ[u].iteritems():
                if v in H_succ:
                    # add both representations of edge: u-v and v-u
                    Hnbrs[v]=datadict
                    H_pred[v][u]=datadict
        # copy node and attribute dictionaries
        H.node=self.node.copy()
        H.graph=self.graph.copy()
        return H
