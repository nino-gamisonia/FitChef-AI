import uuid
from langgraph.types import Command
from agent import build_agent

agent = build_agent()
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
print("🥗 FitChef AI CLI — დაწერეთ 'exit' გასასვლელად")
while True:
    u = input("თქვენ: ").strip()
    if u.lower() in ["exit", "quit"]: break
    res = agent.invoke({"messages": [("user", u)]}, config=config)
    st = agent.get_state(config)
    if st.next:
        ans = input("⚠️ დაადასტურეთ წაშლა (yes/no): ").strip().lower()
        res = agent.invoke(Command(resume=(ans in ["yes", "y", "დიახ"])), config=config)
    print("🤖:", res["messages"][-1].content)
