from mcp.server.fastmcp import FastMCP

import git, os

from urllib.parse import unquote

mcp = FastMCP("Git MCP Server")


@mcp.resource("repository://{repository_path}/summary", name="repository_summary")
def repository_summary(repository_path: str) -> str:
    """Get a summary of the Git repository.

    Args:
        repository_path: path to the repository
    """

    unquote_path = unquote(repository_path)
    
    try:
        git_repo = git.Repo(unquote_path)
        summary = {
            "active_branch": git_repo.active_branch.name,
            "head_commit": git_repo.head.commit.hexsha,
            "message": git_repo.head.commit.message,
            "author": git_repo.head.commit.author.name,
            "date": git_repo.head.commit.committed_datetime.isoformat(),
        }
        return str(summary)
    except git.exc.InvalidGitRepositoryError:
        return f"Error: {unquote_path} is not a valid git repository."
    except Exception as e:
        return f"Excepción getting summary information for {unquote_path}: {str(e)}"

@mcp.prompt()
def git_system_prompt(repository_path: str) -> str:
    """Global instructions for Git Assistant."""
    # Get the absolute path to the prompts directory
    current_dir = os.path.dirname(__file__)
    prompt_path = os.path.join(current_dir, "prompts", "git-prompt.md")
    
    with open(prompt_path, "r", encoding="utf-8") as file:
        template = file.read()
    return template.format(repository_path=repository_path)


@mcp.tool()
def status(repository_path: str) -> str:
    """Shows the working tree status.

    Args:
        repository_path: path to the repository
    """

    try:
        git_repo = git.Repo(repository_path)
        return git_repo.git.status()
    except git.exc.InvalidGitRepositoryError:
        return f"Error: {repository_path} is not a valid git repository"
    except Exception as e:
        return f"Excepción executing status: {str(e)}"
    
@mcp.tool()
def log(repository_path: str) -> str:
    """Shows commit logs.

    Args:
        repository_path: path to the repository
    """

    try:
        git_repo = git.Repo(repository_path)
        return git_repo.git.log()
    except git.exc.InvalidGitRepositoryError:
        return f"Error: {repository_path} is not a valid git repository"
    except Exception as e:
        return f"Excepción executing log: {str(e)}"
 

if __name__ == "__main__":
    mcp.run(transport='stdio')