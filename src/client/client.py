from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from urllib.parse import quote

class MCPStdioClient:
    """It handles communications with MCP Git Server."""
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self._resource_template = None
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

    
        self._response_tools = await self._session.list_tools()
        self._response_prompts = await self._session.list_prompts()
        self._response_resources = await self._session.list_resources()
        self._response_resources_templates = await self._session.list_resource_templates()

        print("\n✅ Connnected to MCP Server:", initialize_result.serverInfo.name)
        print("\n✅ Available tools:", [tool.name for tool in self._response_tools.tools])
        print("\n✅ Available prompts:", [prompt.name for prompt in self._response_prompts.prompts])
        print("\n✅ Available resources:", [resource.name for resource in self._response_resources.resources])
        print("\n✅ Available resource templates:", [resourceTemplates.name for resourceTemplates in self._response_resources_templates.resourceTemplates])
        

    async def get_tools(self):
        response_tools = await self._session.list_tools()
        return response_tools.tools

    async def get_prompt(self, name: str, arguments: dict):
        response = await self._session.get_prompt(name=name, arguments=arguments)
        return response.messages[0].content.text

    async def get_summary_resource(self):
        if self._resource_template is None:
            self._resource_template = next((resource for resource in self._response_resources_templates.resourceTemplates if resource.name == "repository_summary"), None)

        print(self._resource_template)
        uri = self._resource_template.uriTemplate.format(repository_path=quote(self.repo_path, safe=[])) 

        response = await self._session.read_resource(uri=uri)
        return response.contents[0].text

    async def get_resource(self, uri: str):
        return await self._session.read_resource(uri=uri)

    async def call_tool(self, tool_name: str, arguments: dict):
        return await self._session.call_tool(tool_name, arguments)

    async def cleanup(self):
        await self.exit_stack.aclose()