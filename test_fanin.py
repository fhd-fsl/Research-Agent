from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    log: Annotated[list[str], operator.add]

def node_a(state: State):
    return {"log": ["A"]}

def node_b(state: State):
    return {"log": ["B"]}

def node_c(state: State):
    return {"log": ["C"]}

def node_d(state: State):
    return {"log": ["D"]}

builder = StateGraph(State)
builder.add_node("A", node_a)
builder.add_node("B", node_b)
builder.add_node("C", node_c)
builder.add_node("D", node_d)

builder.add_edge(START, "A")
builder.add_edge("A", "B")
builder.add_edge("A", "C")
builder.add_edge("B", "D")
builder.add_edge("C", "D")
builder.add_edge("D", END)

graph = builder.compile()

print(graph.invoke({"log": []}))
