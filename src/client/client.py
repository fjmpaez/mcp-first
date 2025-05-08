from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPStdioClient:
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