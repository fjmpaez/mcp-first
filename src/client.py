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

# Cargar variables de entorno
load_dotenv()

# Primer paso: obtener respuesta inicial del modelo y tool_calls si los hay
MODEL_NAME = "gpt-4"


class MCPClient:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = OpenAI() 

    async def connect_to_server(self, server_script_path: str):
        """Inicia conexión con el servidor MCP por stdio"""
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
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        initialize_result = await self.session.initialize()
        
        response_tools = await self.session.list_tools()
        response_prompts = await self.session.list_prompts()
        response_resources = await self.session.list_resources()
        response_resources_templates = await self.session.list_resource_templates()

        print("\n✅ Conectado al servidor MCP:", initialize_result.serverInfo.name)
        print("\n✅ Herramientas disponibles:", [tool.name for tool in response_tools.tools])
        print("\n✅ Prompts disponibles:", [prompt.name for prompt in response_prompts.prompts])
        print("\n✅ Recursos disponibles:", [resource.name for resource in response_resources.resources])
        print("\n✅ Plantillas de recursos disponibles:", [resourceTemplates.name for resourceTemplates in response_resources_templates.resourceTemplates])
        

        system_prompt_response = await self.session.get_prompt(name="git_system_prompt", arguments={"repository_path": self.repo_path}) 
        self.system_prompt = system_prompt_response.messages[0].content.text
        uri = f"repository://{quote(self.repo_path, safe=[])}/summary"

        self.repository_summary = await self.session.read_resource(uri=uri)

        print("\n✅ Resumen del repositorio:", self.repository_summary)


    async def process_query(self, query: str):
        """Procesa una consulta del usuario"""
        
        response_tools = await self.session.list_tools()
        

        tools = response_tools.tools

        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema
            }
        } for tool in tools]


        # Añadir el resumen del repositorio a la conversación
            

        chat_response = self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": self.system_prompt + "\n\n Repository Summary:" + self.repository_summary.contents[0].text},
                {"role": "user", "content": query}
            ],
            tools=available_tools,
            tool_choice="auto"
        )

        message = chat_response.choices[0].message
        messages = [{"role": "user", "content": query}]

        final_response = message.content

        if message.tool_calls:
            tools_calls_results = []
            tool_messages = []

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                result = await self.session.call_tool(tool_name, arguments)
                tool_output = result.content
                tools_calls_results.append((tool_call, tool_output))

                # Añadir el paso de tool_call y su respuesta al historial
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call.model_dump()]
                })
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_output
                })

            # Segundo paso: enviar los resultados de tools a GPT-4
            refined_response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages + tool_messages
            )

            final_response = refined_response.choices[0].message.content

        
        print(f"\n💬 GPT-4:\n{final_response}")


    async def chat_loop(self):
        """Bucle interactivo"""
        print("\n🧠 Cliente MCP iniciado. Escribe 'quit' para salir.")
        while True:
            try:
                query = input("\n🗨️  Tu consulta: ").strip()
                if query.lower() == 'quit':
                    break
                await self.process_query(query)
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
    
    async def cleanup(self):
        """Cierra recursos"""
        await self.exit_stack.aclose()

async def main():

    parser = argparse.ArgumentParser(description="Run MCP git server.")
    
    parser.add_argument("server_script_path", type=str, help="Path to the server python script.")
    parser.add_argument("repository_path", type=str, help="Path to the git repository.")
    args = parser.parse_args()

        
    client = MCPClient(repo_path=args.repository_path)
    try:
        await client.connect_to_server(args.server_script_path)
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
