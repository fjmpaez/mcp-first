import asyncio
import json
from dotenv import load_dotenv
import argparse
from urllib.parse import quote
from client.client import MCPStdioClient
from model.models import OpenAIClient, ModelClient

# Cargar variables de entorno
load_dotenv()

class Agent:
    """Coordina las interacciones entre el usuario, el servidor MCP y OpenAI."""
    def __init__(self, mcp_client: MCPStdioClient, model_client: ModelClient):
        self._mcp_client = mcp_client
        self._model_client = model_client
        self._system_prompt = ""
        self._repository_summary = ""

    async def initialize(self):
        self._system_prompt = await self._mcp_client.get_prompt(
            name="git_system_prompt",
            arguments={"repository_path": self._mcp_client.repo_path}
        )
        
        self._repository_summary = await self._mcp_client.get_resource(uri=f"repository://{quote(self._mcp_client.repo_path, safe=[])}/summary")
        tools = await self._mcp_client.get_tools()

        self._available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema
            }
        } for tool in tools]

    async def process_query(self, query: str):

        messages = [
            {"role": "system", "content": self._system_prompt + "\n\n Repository Summary:" + self._repository_summary.contents[0].text},
            {"role": "user", "content": query}
        ]

        chat_response = self._model_client.chat_completion(
            messages=messages,
            tools=self._available_tools
        )

        message = chat_response.choices[0].message
        final_response = message.content

        if message.tool_calls:
            tool_messages = []
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                result = await self._mcp_client.call_tool(tool_name, arguments)
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call.model_dump()]
                })
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.content
                })

            refined_response = self._model_client.chat_completion(
                messages=messages + tool_messages
            )

            final_response = refined_response.choices[0].message.content

        print(f"\n💬 GPT-4:\n{final_response}")


async def main():
    parser = argparse.ArgumentParser(description="Run MCP git server.")
    parser.add_argument("server_script_path", type=str, help="Path to the server python script.")
    parser.add_argument("repository_path", type=str, help="Path to the git repository.")
    args = parser.parse_args()

    mcp_client = MCPStdioClient(repo_path=args.repository_path)
    model_client = OpenAIClient()
    agent = Agent(mcp_client, model_client)

    try:
        await mcp_client.connect(args.server_script_path)
        await agent.initialize()

        print("\n🧠 Cliente MCP iniciado. Escribe 'quit' para salir.")
        while True:
            query = input("\n🗨️  Tu consulta: ").strip()
            if query.lower() == 'quit':
                break
            await agent.process_query(query)
    finally:
        await mcp_client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())