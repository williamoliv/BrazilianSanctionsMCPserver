import asyncio
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain.messages import HumanMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

async def main():
    # Connect to MCP server
    client = MultiServerMCPClient(
        {
            "brazilian_sanctions": {
                "command": "python",
                "args": ["mcp_server.py"],
                "transport": "stdio",
            }
        }
    )
    
    # Get tools from MCP server
    tools = await client.get_tools()

    llm = ChatOllama(
        model="qwen3:8b",
        temperature=0
    )
    
    system_prompt = "You are a helpful assistant that can search Brazilian sanctions databases. Use the available tools to find information about sanctioned entities and individuals. Provide detailed information including sanction reasons, dates, and agencies when available."

    agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)
    
    async def start_chat():
        print("Welcome to Brazilian Sanctions Chatbot! Type 'exit' to quit.")
        config = {"configurable": {"thread_id": "chat_session"}}
        while True:
            user_input = input("You: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            response = await agent.ainvoke({"messages": [HumanMessage(content=user_input)]}, config=config)
            print(f"Agent: {response['messages'][-1].content}\n")

    await start_chat()

if __name__ == "__main__":
    asyncio.run(main())