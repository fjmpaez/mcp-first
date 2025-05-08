# Git Executor MCP Server and client.

## Description
This is a simple example of a MCP server for interacting with a git repository. The server has been created using Python SDK: https://github.com/modelcontextprotocol/python-sdk

The repository is create as reference on https://adictosaltrabajo.com tutorial.

It includes just two git tools, one prompt and one resource.

## Installation
```bash
   git clone https://github.com/fjmpaez/mcp-first.git
   cd mcp-git-server
   poetry install
```

## Usage
```bash
poetry run python src/git-explorer.py  ./src/git_server/main.py absolute_path_to_git_repo
```

