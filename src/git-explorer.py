import asyncio
import json
from typing import Optional
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
import argparse
from urllib.parse import quote
from abc import ABC, abstractmethod

# Cargar variables de entorno
load_dotenv()


class MCPClient:
    """It handles communications with MCP Git Server."""
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self._session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect(self, server_script_path: str):
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("El script debe ser .py o .js")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        self._session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        
        initialize_result = await self._session.initialize()

    
        response_tools = await self._session.list_tools()
        response_prompts = await self._session.list_prompts()
        response_resources = await self._session.list_resources()
        response_resources_templates = await self._session.list_resource_templates()

        print("\n✅ Connnected to MCP Server:", initialize_result.serverInfo.name)
        print("\n✅ Available tools:", [tool.name for tool in response_tools.tools])
        print("\n✅ Available prompts:", [prompt.name for prompt in response_prompts.prompts])
        print("\n✅ Available resources:", [resource.name for resource in response_resources.resources])
        print("\n✅ Available resource templates:", [resourceTemplates.name for resourceTemplates in response_resources_templates.resourceTemplates])
        

    async def get_tools(self):
        response_tools = await self._session.list_tools()
        return response_tools.tools

    async def get_prompt(self, name: str, arguments: dict):
        response = await self._session.get_prompt(name=name, arguments=arguments)
        return response.messages[0].content.text

    async def get_resource(self, uri: str):
        return await self._session.read_resource(uri=uri)

    async def call_tool(self, tool_name: str, arguments: dict):
        return await self._session.call_tool(tool_name, arguments)

    async def cleanup(self):
        await self.exit_stack.aclose()


class ModelClient(ABC):
    """Model Client."""
    
    @abstractmethod
    def chat_completion(self, messages: list[dict], tools: list[dict] = None):
        """It sends a chat completion request to the model."""
        pass

class OpenAIClient(ModelClient):
    """OpenAI Model Client."""
    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name
        self.client = OpenAI()

    def chat_completion(self, messages:list, tools: list = None):
        
        args = {
            "model": self.model_name,
            "messages": messages,
        }

        if tools:
            args["tools"] = tools
            args["tool_choice"] = "auto"


        return self.client.chat.completions.create(**args)
    


class Agent:
    """Coordina las interacciones entre el usuario, el servidor MCP y OpenAI."""
    def __init__(self, mcp_client: MCPClient, model_client: ModelClient):
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

    mcp_client = MCPClient(repo_path=args.repository_path)
    openai_client = OpenAIClient()
    agent = Agent(mcp_client, openai_client)

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