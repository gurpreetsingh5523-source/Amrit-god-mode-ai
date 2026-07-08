import json
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import re
import os

@dataclass
class LearningResult:
    topic: str
    repos: List[str]
    patterns: List[str]
    timestamp: str

class GitHubLearner:
    def __init__(self, data_file: str = "learning_data.json"):
        self.data_file = data_file
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """Create data file if it doesn't exist."""
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump([], f)
    
    def _load_existing_data(self) -> List[Dict]:
        """Load existing learning data from JSON file."""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_result(self, result: LearningResult):
        """Append learning result to JSON file."""
        data = self._load_existing_data()
        data.append(asdict(result))
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def recall_patterns(self, topic: str) -> Optional[Dict]:
        """Recall previously learned patterns for a topic."""
        data = self._load_existing_data()
        for entry in reversed(data):
            if entry['topic'].lower() == topic.lower():
                return entry
        return None
    
    def _validate_repo_url(self, url: str) -> Optional[str]:
        """Validate and extract repo path from GitHub URL."""
        pattern = r'https?://github\.com/([^/]+/[^/]+?)(?:/.*)?$'
        match = re.match(pattern, url)
        if match:
            return match.group(1)
        return None
    
    # Curated high-reach agent repos to learn architecture/capabilities from.
    AGENT_REPOS = [
        "FoundationAgents/MetaGPT",     # multi-agent software company (closest to Amrit)
        "microsoft/autogen",            # agentic AI programming framework
        "crewAIInc/crewAI",             # role-playing autonomous agent orchestration
        "langchain-ai/langgraph",       # resilient agent graphs
        "NousResearch/hermes-agent",    # OpenAI-compatible agent gateway
    ]

    def learn_agent_repos(self, max_files: int = 3) -> list:
        """Learn architecture/capability patterns from the curated agent repos."""
        results = []
        for repo in self.AGENT_REPOS:
            topic = "agent:" + repo.split("/")[-1]
            if self.recall_patterns(topic):
                results.append((topic, "cached"))
                continue
            files = self.fetch_files(repo, ["README.md", "*.md"], max_files=max_files)
            patterns = []
            for path, content in list(files.items())[:max_files]:
                patterns.extend(self.extract_patterns(content[:2500], topic).get("patterns", []))
            if patterns:
                self._save_result(LearningResult(topic=topic, repos=[repo],
                                  patterns=patterns[:15], timestamp=datetime.now().isoformat()))
            results.append((topic, len(patterns)))
        return results

    # affaan-m/ECC — a 37-skill curated agent-skill library (SKILL.md format).
    # These are the skills most relevant to Amrit's own work.
    ECC_SKILLS = [
        "agent-introspection-debugging", "tdd-workflow", "verification-loop",
        "eval-harness", "api-design", "backend-patterns", "frontend-patterns",
        "security-review", "deep-research", "coding-standards",
        "mcp-server-patterns", "e2e-testing", "benchmark-methodology",
    ]

    def learn_ecc_skills(self, skills: List[str] = None) -> list:
        """Ingest curated SKILL.md instructions from affaan-m/ECC into Amrit's
        learned knowledge so its coder can recall real, battle-tested skills."""
        skills = skills or self.ECC_SKILLS
        results = []
        for name in skills:
            topic = "ecc:" + name
            if self.recall_patterns(topic):
                results.append((topic, "cached")); continue
            url = f"https://raw.githubusercontent.com/affaan-m/ECC/main/.agents/skills/{name}/SKILL.md"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GitHubLearner/1.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    content = r.read().decode("utf-8", "replace")
            except Exception as e:
                results.append((topic, f"fetch-fail")); continue
            patterns = self.extract_patterns(content[:3000], f"{name} skill").get("patterns", [])
            if patterns:
                self._save_result(LearningResult(topic=topic, repos=["affaan-m/ECC"],
                                  patterns=patterns[:15], timestamp=datetime.now().isoformat()))
            results.append((topic, len(patterns)))
        return results

    def search_repos(self, topic: str, max_repos: int = 3) -> List[str]:
        """Search GitHub for repositories related to a topic."""
        repos = []
        query = topic.replace(' ', '+')
        search_url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={max_repos}"
        
        try:
            req = urllib.request.Request(search_url, headers={
                "User-Agent": "GitHubLearner/1.0",
                "Accept": "application/vnd.github.v3+json"
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
                for item in data.get("items", [])[:max_repos]:
                    repos.append(item["full_name"])
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            print(f"Warning: Could not search repos for {topic}: {e}")
        
        return repos
    
    def fetch_files(self, repo_path: str, patterns: List[str], max_files: int = 4) -> Dict[str, str]:
        """Fetch files from a GitHub repo matching given patterns."""
        files_content = {}
        
        # Try to get the repo's file tree from GitHub API
        api_url = f"https://api.github.com/repos/{repo_path}/git/trees/main?recursive=1"
        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "GitHubLearner/1.0",
                "Accept": "application/vnd.github.v3+json"
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                tree_data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError):
            # Try 'master' branch instead
            try:
                api_url = f"https://api.github.com/repos/{repo_path}/git/trees/master?recursive=1"
                req = urllib.request.Request(api_url, headers={
                    "User-Agent": "GitHubLearner/1.0",
                    "Accept": "application/vnd.github.v3+json"
                })
                with urllib.request.urlopen(req, timeout=15) as response:
                    tree_data = json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
                print(f"Warning: Could not fetch file tree for {repo_path}: {e}")
                return {}
        
        # Collect matching files, SKIP boilerplate (.github/, CONTRIBUTING, issue
        # templates, LICENSE...) which is meta-noise, and PRIORITISE real
        # docs/source (README → docs/ → src/) so the capped fetch learns API/arch,
        # not PR-label rules.
        _JUNK = (".github/", "contributing", "code_of_conduct", "issue_template",
                 "pull_request_template", "license", "changelog", "security.md",
                 "funding", ".gitignore")
        def _priority(p):
            pl = p.lower()
            if pl == "readme.md" or pl.endswith("/readme.md"): return 0
            if pl.startswith(("docs/", "doc/", "examples/", "example/")): return 1
            if pl.startswith(("src/", "lib/")): return 2
            return 3
        candidates = [it["path"] for it in tree_data.get("tree", [])
                      if it.get("type") == "blob"
                      and self._matches_pattern(it["path"], patterns)
                      and not any(j in it["path"].lower() for j in _JUNK)]
        candidates.sort(key=_priority)

        for file_path in candidates:
            if len(files_content) >= max_files:
                break

            # Fetch raw file content
            raw_url = f"https://raw.githubusercontent.com/{repo_path}/main/{file_path}"
            try:
                req = urllib.request.Request(raw_url, headers={
                    "User-Agent": "GitHubLearner/1.0"
                })
                with urllib.request.urlopen(req, timeout=15) as response:
                    content = response.read().decode("utf-8", errors="replace")
                    files_content[file_path] = content
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                # Try master branch
                try:
                    raw_url = f"https://raw.githubusercontent.com/{repo_path}/master/{file_path}"
                    req = urllib.request.Request(raw_url, headers={
                        "User-Agent": "GitHubLearner/1.0"
                    })
                    with urllib.request.urlopen(req, timeout=15) as response:
                        content = response.read().decode("utf-8", errors="replace")
                        files_content[file_path] = content
                except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                    continue
        
        return files_content
    
    def _matches_pattern(self, file_path: str, patterns: List[str]) -> bool:
        """Check if a file path matches any of the given patterns."""
        for pattern in patterns:
            # Simple glob matching
            if pattern.startswith("*."):
                ext = pattern[1:]
                if file_path.endswith(ext):
                    return True
            elif pattern in file_path:
                return True
        return False
    
    def extract_patterns(self, code: str, topic: str) -> Dict[str, Any]:
        """Use LLM to summarize correct API usage and reusable patterns."""
        if not code.strip():
            return {"patterns": [], "api_usage": [], "summary": "No code provided"}
        
        prompt = (
            f"From this source/docs about '{topic}', extract concrete, reusable knowledge.\n"
            f"Return 5-10 short bullet lines: real API methods/functions (with correct names), "
            f"usage patterns, and pitfalls. One fact per line, no preamble.\n\n"
            f"CONTENT:\n{code[:2500]}"
        )
        # REAL LLM call (was a placeholder stub before — that's why it learned nothing).
        try:
            import asyncio
            from llm_router import LLMRouter
            if not hasattr(self, "_router") or self._router is None:
                self._router = LLMRouter()
            text = asyncio.run(self._router.complete(prompt, max_tokens=500))
            patterns = [ln.strip(" -•\t") for ln in (text or "").splitlines()
                        if ln.strip(" -•\t")][:10]
        except Exception as e:
            patterns = []
            return {"patterns": [], "api_usage": [], "summary": f"LLM error: {e}"}

        # also capture import/def lines as structured api_usage (cheap static signal)
        api_usage = [l.strip() for l in code.split('\n')
                     if l.strip().startswith(('import ', 'from ')) or 'def ' in l][:10]
        return {
            "patterns": patterns,
            "api_usage": api_usage,
            "summary": f"Learned {len(patterns)} patterns about {topic}",
        }
    
    def learn(self, topic: str, max_repos: int = 3, max_files: int = 5, patterns: List[str] = None) -> LearningResult:
        """Main learning method: search, fetch, extract, and save patterns."""
        if patterns is None:
            # READMEs/docs hold the real API examples — learn those first.
            patterns = ["README.md", "*.md", "*.js", "*.py", "*.ts"]
        
        # Check for existing knowledge
        existing = self.recall_patterns(topic)
        if existing:
            print(f"Found existing knowledge for '{topic}'")
            return LearningResult(**existing)
        
        # Search for repositories
        repos = self.search_repos(topic, max_repos)
        if not repos:
            print(f"No repositories found for '{topic}'")
            return LearningResult(topic=topic, repos=[], patterns=[], timestamp=datetime.now().isoformat())
        
        # Fetch files from repositories
        all_patterns = []
        for repo in repos[:max_repos]:
            files = self.fetch_files(repo, patterns, max_files=max_files)
            file_count = 0
            for file_path, content in files.items():
                if file_count >= max_files:
                    break
                
                # Truncate content for LLM
                truncated_content = content[:2000]
                
                # Extract patterns
                result = self.extract_patterns(truncated_content, topic)
                all_patterns.extend(result.get("patterns", []))
                file_count += 1
            
            if file_count >= max_files:
                break
        
        # Create result
        result = LearningResult(
            topic=topic,
            repos=repos[:max_repos],
            patterns=list(set(all_patterns))[:20],  # Deduplicate and limit
            timestamp=datetime.now().isoformat()
        )
        
        # Save to JSON file
        self._save_result(result)
        
        return result

# Example usage
if __name__ == "__main__":
    learner = GitHubLearner()
    
    # Learn about a topic
    result = learner.learn("machine learning")
    print(f"Learned about: {result.topic}")
    print(f"From repos: {result.repos}")
    print(f"Found {len(result.patterns)} patterns")
    
    # Recall later
    recalled = learner.recall_patterns("machine learning")
    if recalled:
        print(f"Recalled: {recalled['topic']} - {len(recalled['patterns'])} patterns")