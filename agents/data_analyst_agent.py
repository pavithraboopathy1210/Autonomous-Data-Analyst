
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from tools.dataset_tools import dataset_tools, set_active_dataset

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")


SYSTEM_PROMPT = """
You are an autonomous data analyst.

Your responsibility is to answer questions using the actual dataset.

Rules:

1. Always use Python tools when a question requires dataset
   information or calculations.

2. Never invent values, statistics, or results.

3. Select the most appropriate tool for each question.

4. Use dataset_overview_tool for general dataset information.

5. Use missing_values_tool for missing value analysis.

6. Use numerical_summary_tool for numerical statistics.

7. Use grouped_analysis_tool for grouped calculations such as
   total sales by product or category.

8. Use correlation_tool for correlation questions.

9. Use frequency_analysis_tool for frequency analysis.

10. Use highest_value_record_tool when the user asks for the
    highest individual transaction, order, sale, or record.

11. When asked which product generated the highest individual
    sales amount, first find the highest individual record using
    highest_value_record_tool. Then identify the product from
    that record.

12. Do not use grouped product totals to answer questions about
    the highest individual transaction.

13. Remember previous messages and understand follow-up questions.

14. Use previous conversation context when resolving references
    such as "it", "that product", or "those results".

15. Explain results clearly in simple language.

16. If requested information is unavailable, say so.
"""


def create_gemini_model():
    return ChatGoogleGenerativeAI(
        model="gemini-flash-lite-latest",
        api_key=API_KEY,
        temperature=0
    )


def create_data_analyst_agent(df):

    if df is None or df.empty:
        raise ValueError("Dataset is empty or not loaded.")

    set_active_dataset(df)

    model = create_gemini_model()
    memory = MemorySaver()

    agent = create_react_agent(
        model=model,
        tools=dataset_tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=memory
    )

    return agent


def ask_agent(agent, question, thread_id="dataset_session"):

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": question.strip()
                }
            ]
        },
        config={
            "configurable": {
                "thread_id": thread_id
            }
        }
    )

    print("\n========== AGENT EXECUTION TRACE ==========")

    for message in result["messages"]:

        tool_calls = getattr(message, "tool_calls", [])

        if tool_calls:
            for call in tool_calls:
                print(f"\n[TOOL CALLED] {call['name']}")
                print(f"[TOOL INPUT] {call['args']}")

        if getattr(message, "type", None) == "tool":
            print(f"\n[TOOL RESULT] {message.content}")

    print("\n========== END OF EXECUTION TRACE ==========\n")

    final_message = None

    for message in reversed(result["messages"]):
        if (
            getattr(message, "type", None) == "ai"
            and not getattr(message, "tool_calls", [])
        ):
            final_message = message
            break

    if final_message is None:
        final_message = result["messages"][-1]

    content = final_message.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]

        return "\n".join(part for part in text_parts if part) or str(content)

    return str(content)
