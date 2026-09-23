from langchain_core.messages import HumanMessage
from agent import graph

result = graph.astream_events({
    "messages": [HumanMessage(content="3 olive hoodies, size M, to pincode 560001")]
})

# print just the last message
print(result)
