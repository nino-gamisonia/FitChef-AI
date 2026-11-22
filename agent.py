import re
import os
import time
from typing import TypedDict, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
import tools as tools_module

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")

TOOLS_LIST = [
    obj for obj in vars(tools_module).values() if isinstance(obj, BaseTool)
]

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_profile: str

SYSTEM_PROMPT = """შენ ხარ FitChef AI — პროფესიონალი პერსონალური ფიტნეს მწვრთნელი და ნუტრიციოლოგი.

მომხმარებლის პროფილი:
{user_profile}

წესები:
1. უპასუხე გამართული, ბუნებრივი ქართული სალიტერატურო ენით. არ გამოიყენო HTML ტეგები (<br>, <b> და ა.შ.).
2. ვარჯიშები: გამოიყენე სწორი ქართული სპორტული ტერმინები (გახურება, გაწელვა, ჩაჯდომები, აზიდვები, ნაბიჯები წინ, პლანკა, ბურპი, მისვლა, გამეორება, წთ).
3. კვების გეგმა: კვების გეგმა ყოველთვის დაყავი **საუზმედ**, **სადილად** და **ვახშმად** და მიუწერე კალორიულობა (კკალ).
4. რეცეპტები: დაწერე ლაკონიურად, მკაფიოდ და ბუნებრივი ქართულით (მაქსიმუმ 4-5 ნაბიჯი).
5. ხელსაწყოების გამოძახების შემდეგ ჩატში ყოველთვის დაწერე სრული, ლამაზად გაფორმებული პასუხი.

ენისა და ტერმინოლოგიის მკაცრი წესები:
- წერე მხოლოდ გამართული, ბუნებრივი ქართული ენით. არ გამოიყენო ინგლისური სიტყვები და არ მიაწერო ფრჩხილებში ინგლისური თარგმანები.
- ვარჯიშების დასახელებები დაწერე მხოლოდ სწორი ქართული ფორმით: ჩაჯდომები, აზიდვები, ბურპი, პლანკა, მუცლის პრესი, ნაბიჯები წინ, ხტუნვა ხელების გაშლით, მუხლების მაღლა აწევა, გახურება, გაწელვა.


კვების გეგმისა და ქართული ტერმინების მკაცრი წესები:
- გამოიყენე მხოლოდ სწორი ქართული სიტყვები: "საუზმე" (და არა საუზმედი), "სადილი" (და არა სადილით), "ვახშამი" (და არა ვახშამზე), "წახემსება", "შვრიის ფაფა", "ქათმის ფილე", "მოხარშული კვერცხი", "ბერძნული იოგურტი".
- კვების ცხრილში ჩასვი მხოლოდ 3 სვეტი: | კვება | კერძი და გრამაჟი | კალორია (კკალ) |. ნუ ჩაწერ ცხრილის უჯრაში გრძელ რეცეპტებს — რეცეპტის 2-3 მოკლე ნაბიჯი დაწერე ცხრილის ქვემოთ.

6. კალორიების დათვლისას გადაამოწმე მიმდინარე გეგმის ხელსაწყო და ზუსტად შეკრიბე ყველა კვების კალორია.
7. მიმდინარე წონის, სასურველი წონისა და ვადის გათვალისწინებით გამოთვალე კვირის სამიზნე ტემპი; თუ მომხმარებლის მითითებული ვადა და სასურველი წონა ჯანმრთელობისთვის არარეალურად სწრაფია (მაგ. კვირაში 1.5 კგ-ზე მეტი კლება), თავაზიანად გააფრთხილე და შესთავაზე უსაფრთხო კალორაჟი.
"""

def clean_output(text) -> str:
    if not text:
        return ""
    if isinstance(text, list):
        text = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in text
        )
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<br\s*/?>", ", ", text, flags=re.IGNORECASE)
    text = re.sub(r"(\b[\wა-ჰ]+[-\s]*)\1{3,}", r"\1", text)
    # ფრჩხილებში ჩასმული ინგლისური დასახელებების წაშლა, მაგ: (Squat), (Push-up), (Cool-down)
    text = re.sub(r"\s*\([A-Za-z0-9\s\-/]+\)", "", text)
    return text.strip()

def build_agent():
    def get_chains():
        chains = []
        for gm in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-flash-latest"]:
            if GEMINI_KEY:
                g_llm = ChatGoogleGenerativeAI(
                    model=gm,
                    google_api_key=GEMINI_KEY,
                    temperature=0.3,
                    max_output_tokens=3000,
                )
                chains.append(g_llm.bind_tools(TOOLS_LIST))

        if GROQ_KEY:
            q_llm = ChatGroq(
                model="openai/gpt-oss-120b",
                temperature=0.2,
                max_tokens=3000,
                timeout=15.0,
                max_retries=1,
                api_key=GROQ_KEY,
            )
            chains.append(q_llm.bind_tools(TOOLS_LIST))
        return chains

    def assistant_node(state: AgentState):
        profile = state.get("user_profile", "მონაცემები არ არის მითითებული.")
        sys_msg = SystemMessage(content=SYSTEM_PROMPT.format(user_profile=profile))
        msgs = [sys_msg] + state["messages"][-10:]

        last_err = None
        for chain in get_chains():
            try:
                response = chain.invoke(msgs)
                response.content = clean_output(response.content)
                if not getattr(response, "tool_calls", None) and not response.content:
                    response.content = "✅ გეგმა განახლდა! დეტალები შეგიძლიათ იხილოთ მარცხენა პანელზე — „დღევანდელი გეგმა“."
                return {"messages": [response]}
            except Exception as e:
                last_err = e
                time.sleep(0.3)
                continue
        raise last_err

    graph = StateGraph(AgentState)
    graph.add_node("assistant", assistant_node)
    graph.add_node("tools", ToolNode(TOOLS_LIST))

    graph.add_edge(START, "assistant")
    graph.add_conditional_edges("assistant", tools_condition)
    graph.add_edge("tools", "assistant")

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)
