import subprocess

class GitOps:
    """Git operations for repository management and version control."""
    
    @staticmethod
    def clone_repo(repo_url: str, local_path: str):
        """Clone a git repository."""
        cmd = ['git', 'clone', repo_url, local_path]
        subprocess.run(cmd, check=True)
    
    @staticmethod
    def commit(message: str, repo_path: str = '.'):
        """Commit changes with a message."""
        subprocess.run(['git', '-C', repo_path, 'add', '.'], check=True)
        subprocess.run(['git', '-C', repo_path, 'commit', '-m', message], check=True)
    
    @staticmethod
    def push(branch: str = 'main', repo_path: str = '.'):  
        """Push changes to remote."""
        subprocess.run(['git', '-C', repo_path, 'push', 'origin', branch], check=True)
    
    @staticmethod
    def pull(branch: str = 'main', repo_path: str = '.'):  
        """Pull changes from remote."""
        subprocess.run(['git', '-C', repo_path, 'pull', 'origin', branch], check=True)
    
    @staticmethod
    def create_branch(branch_name: str, repo_path: str = '.'):  
        """Create a new branch."""
        subprocess.run(['git', '-C', repo_path, 'checkout', '-b', branch_name], check=True)
    
    @staticmethod
    def switch_branch(branch_name: str, repo_path: str = '.'):  
        """Switch to a different branch."""
        subprocess.run(['git', '-C', repo_path, 'checkout', branch_name], check=True)
    
    @staticmethod
    def get_status(repo_path: str = '.') -> str:  
        """Get repository status."""
        result = subprocess.run(['git', '-C', repo_path, 'status'], capture_output=True, text=True)
        return result.stdout  
    
    @staticmethod
    def get_log(repo_path: str = '.', limit: int = 10) -> str:  
        """Get commit log."""
        result = subprocess.run(['git', '-C', repo_path, 'log', f'-{limit}', '--oneline'], capture_output=True, text=True)
        return result.stdout