"""
github_integration.py - GitHub integration for self-improvement capabilities
"""

import os
import logging
import aiohttp
import asyncio
import base64
from typing import Dict, Any, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GitHubIntegration")

class GitHubClient:
    """Client for interacting with the GitHub API"""
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the GitHub client
        
        Args:
            github_token: GitHub API token, if None will look for GITHUB_TOKEN env var
        """
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        if not self.github_token:
            logger.warning("No GitHub token provided, limited functionality available")
        
        self.api_base_url = "https://api.github.com"
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session with GitHub auth headers"""
        if self.session is None or self.session.closed:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            if self.github_token:
                headers["Authorization"] = f"Bearer {self.github_token}"
                
            self.session = aiohttp.ClientSession(headers=headers)
        
        return self.session
    
    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Get repository information
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            
        Returns:
            Repository information
        """
        session = await self._get_session()
        url = f"{self.api_base_url}/repos/{owner}/{repo}"
        
        async with session.get(url) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Error getting repository: {error_text}")
            
            return await response.json()
    
    async def get_file_contents(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> Tuple[str, str]:
        """
        Get file contents from a repository
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            path: File path in the repository
            ref: Git reference (branch, tag, commit)
            
        Returns:
            Tuple of (content, sha)
        """
        session = await self._get_session()
        url = f"{self.api_base_url}/repos/{owner}/{repo}/contents/{path}"
        
        params = {}
        if ref:
            params["ref"] = ref
        
        async with session.get(url, params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Error getting file contents: {error_text}")
            
            data = await response.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, data["sha"]
    
    async def create_or_update_file(self, 
                               owner: str, 
                               repo: str, 
                               path: str, 
                               content: str, 
                               message: str, 
                               branch: str,
                               sha: Optional[str] = None) -> Dict[str, Any]:
        """
        Create or update a file in a repository
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            path: File path in the repository
            content: New file content
            message: Commit message
            branch: Branch to commit to
            sha: SHA of the file being replaced (for updates)
            
        Returns:
            Response data from GitHub API
        """
        session = await self._get_session()
        url = f"{self.api_base_url}/repos/{owner}/{repo}/contents/{path}"
        
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        # Prepare request data
        data = {
            "message": message,
            "content": encoded_content,
            "branch": branch
        }
        
        # If SHA is provided, this is an update
        if sha:
            data["sha"] = sha
        
        async with session.put(url, json=data) as response:
            if response.status not in (200, 201):
                error_text = await response.text()
                raise RuntimeError(f"Error creating/updating file: {error_text}")
            
            return await response.json()
    
    async def create_branch(self, 
                      owner: str, 
                      repo: str, 
                      branch: str, 
                      source_branch: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new branch in a repository
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            branch: Name for the new branch
            source_branch: Branch to create from (default: default branch)
            
        Returns:
            Response data from GitHub API
        """
        session = await self._get_session()
        
        # First, get the source branch reference
        if not source_branch:
            # Get the default branch
            repo_info = await self.get_repository(owner, repo)
            source_branch = repo_info["default_branch"]
        
        # Get the source branch SHA
        url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{source_branch}"
        async with session.get(url) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Error getting source branch: {error_text}")
            
            source_data = await response.json()
            source_sha = source_data["object"]["sha"]
        
        # Create the new branch
        url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs"
        data = {
            "ref": f"refs/heads/{branch}",
            "sha": source_sha
        }
        
        async with session.post(url, json=data) as response:
            if response.status != 201:
                error_text = await response.text()
                raise RuntimeError(f"Error creating branch: {error_text}")
            
            return await response.json()
    
    async def create_pull_request(self, 
                            owner: str, 
                            repo: str, 
                            title: str, 
                            body: str, 
                            head: str, 
                            base: str,
                            draft: bool = False) -> Dict[str, Any]:
        """
        Create a new pull request
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            title: PR title
            body: PR body/description
            head: Branch with changes
            base: Branch to merge into
            draft: Whether to create a draft PR
            
        Returns:
            Response data from GitHub API
        """
        session = await self._get_session()
        url = f"{self.api_base_url}/repos/{owner}/{repo}/pulls"
        
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft
        }
        
        async with session.post(url, json=data) as response:
            if response.status != 201:
                error_text = await response.text()
                raise RuntimeError(f"Error creating pull request: {error_text}")
            
            return await response.json()
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()

# Example usage for self-improvement capability
async def suggest_code_improvement(
    owner: str,
    repo: str,
    file_path: str,
    suggested_changes: Dict[str, str],
    title: str,
    description: str,
    branch_name: str = "auto-improvement",
    base_branch: str = "main"
) -> str:
    """
    Suggest code improvements via a GitHub pull request
    
    Args:
        owner: Repository owner
        repo: Repository name
        file_path: Path to the file to improve
        suggested_changes: Dict of "old code" -> "new code" replacements
        title: PR title
        description: PR description
        branch_name: Name for the new branch
        base_branch: Base branch to create PR against (default: main)
        
    Returns:
        URL of the created pull request
    """
    github = GitHubClient()
    
    try:
        # Check if GitHub token is available
        if not github.github_token:
            return "Error: GitHub token not available. Set GITHUB_TOKEN environment variable."
        
        # Validate input
        if not owner or not repo:
            return "Error: Repository owner and name are required"
        
        if not file_path:
            return "Error: File path is required"
        
        if not suggested_changes:
            return "Error: No changes provided"
            
        try:
            # Create a new branch
            logger.info(f"Creating branch {branch_name} from {base_branch}")
            await github.create_branch(owner, repo, branch_name, source_branch=base_branch)
            
            # Get the current file content
            logger.info(f"Getting content for {file_path}")
            content, sha = await github.get_file_contents(owner, repo, file_path, ref=base_branch)
            
            # Apply suggested changes
            original_content = content
            for old_code, new_code in suggested_changes.items():
                if old_code not in content:
                    logger.warning(f"Could not find text '{old_code[:30]}...' in file")
                    continue
                content = content.replace(old_code, new_code)
            
            # Check if any changes were made
            if content == original_content:
                return "No changes could be applied - check that the suggested changes match the file content"
            
            # Update the file in the new branch
            commit_message = f"Improve {file_path}\n\n{title}"
            logger.info(f"Updating file {file_path} in branch {branch_name}")
            await github.create_or_update_file(
                owner, repo, file_path, content, commit_message, branch_name, sha
            )
            
            # Create a pull request
            logger.info(f"Creating PR from {branch_name} to {base_branch}")
            pr = await github.create_pull_request(
                owner, repo, title, description, branch_name, base_branch
            )
            
            return pr["html_url"]
        except Exception as e:
            logger.error(f"Error in suggest_code_improvement: {str(e)}")
            return f"Error: {str(e)}"
    finally:
        await github.close()

# Example async function to run the self-improvement
async def main():
    pr_url = await suggest_code_improvement(
        owner="your-username",
        repo="your-repo",
        file_path="example.py",
        suggested_changes={
            "def old_function():\n    return 'old'": "def improved_function():\n    return 'improved'"
        },
        title="Improve function implementation",
        description="This PR improves the function implementation by making it more descriptive."
    )
    print(f"Created pull request: {pr_url}")

if __name__ == "__main__":
    asyncio.run(main())