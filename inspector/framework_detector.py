import json
import re
from typing import List, Dict, Set, Optional

# Knowledge base of frameworks, libraries, and devops tools
FRAMEWORK_CATALOG = {
    "Web Frameworks": {
        # Python
        "Django": [r"\bdjango\b"],
        "FastAPI": [r"\bfastapi\b"],
        "Flask": [r"\bflask\b"],
        "Starlette": [r"\bstarlette\b"],
        "Tornado": [r"\btornado\b"],
        "Sanic": [r"\bsanic\b"],
        # Node/JS/TS
        "React": [r"\breact\b", r"\breact-dom\b"],
        "Next.js": [r"\bnext\b"],
        "Vue": [r"\bvue\b"],
        "Nuxt": [r"\bnuxt\b"],
        "Angular": [r"@angular/core"],
        "Svelte": [r"\bsvelte\b"],
        "SvelteKit": [r"@sveltejs/kit"],
        "Astro": [r"\bastro\b"],
        "Remix": [r"@remix-run/"],
        "Express": [r"\bexpress\b"],
        "NestJS": [r"@nestjs/core"],
        "Fastify": [r"\bfastify\b"],
        "Hono": [r"\bhono\b"],
        # Rust
        "Actix-web": [r"\bactix-web\b"],
        "Axum": [r"\baxum\b"],
        "Rocket": [r"\brocket\b"],
        # Go
        "Gin": [r"github\.com/gin-gonic/gin"],
        "Echo": [r"github\.com/labstack/echo"],
        "Fiber": [r"github\.com/gofiber/fiber"],
        "Chi": [r"github\.com/go-chi/chi"],
        # Others
        "Spring Boot": [r"spring-boot"],
        "Laravel": [r"laravel/framework"],
        "Symfony": [r"symfony/"],
        "Ruby on Rails": [r"\brails\b"]
    },
    "AI / Data Science & ML": {
        "PyTorch": [r"\btorch\b", r"\btorchvision\b"],
        "TensorFlow": [r"\btensorflow\b"],
        "Keras": [r"\bkeras\b"],
        "Scikit-learn": [r"\bscikit-learn\b", r"\bsklearn\b"],
        "HuggingFace": [r"\btransformers\b", r"\bdiffusers\b", r"\bdatasets\b"],
        "LangChain": [r"\blangchain\b"],
        "LlamaIndex": [r"\bllama-index\b", r"\bllamaindex\b"],
        "OpenAI SDK": [r"\bopenai\b"],
        "Anthropic SDK": [r"\banthropic\b"],
        "Pandas": [r"\bpandas\b"],
        "NumPy": [r"\bnumpy\b"],
        "Streamlit": [r"\bstreamlit\b"],
        "Gradio": [r"\bgradio\b"],
        "OpenCV": [r"\bopencv-python\b", r"\bcv2\b"],
        "vLLM": [r"\bvllm\b"],
        "Ollama": [r"\bollama\b"]
    },
    "Databases & ORMs": {
        "SQLAlchemy": [r"\bsqlalchemy\b"],
        "Prisma": [r"\bprisma\b", r"@prisma/client"],
        "Mongoose": [r"\bmongoose\b"],
        "TypeORM": [r"\btypeorm\b"],
        "Drizzle ORM": [r"\bdrizzle-orm\b"],
        "Diesel (Rust)": [r"\bdiesel\b"],
        "SQLx (Rust)": [r"\bsqlx\b"],
        "GORM (Go)": [r"gorm\.io/gorm"],
        "Redis": [r"\bredis\b", r"\bioredis\b"],
        "Supabase": [r"@supabase/supabase-js", r"\bsupabase\b"],
        "Firebase": [r"\bfirebase\b", r"firebase-admin"]
    },
    "DevOps & Infrastructure": {
        "Docker": [r"dockerfile", r"docker-compose"],
        "Kubernetes": [r"\bk8s\b", r"kubernetes", r"helm"],
        "GitHub Actions": [r"\.github/workflows"],
        "Terraform": [r"\.tf\b", r"terraform"],
        "Tailwind CSS": [r"\btailwindcss\b"],
        "Vite": [r"\bvite\b"],
        "Webpack": [r"\bwebpack\b"],
        "Celery": [r"\bcelery\b"],
        "Electron": [r"\belectron\b"],
        "Tauri": [r"\btauri\b", r"@tauri-apps/api"]
    }
}

class FrameworkDetector:
    def __init__(self, client):
        self.client = client

    def detect(self, owner: str, repo: str, root_files: List[str]) -> Dict[str, List[str]]:
        """
        Scan repository files and detect frameworks and technologies.
        Returns: Dict mapping category -> list of detected frameworks/tools.
        """
        detected: Dict[str, Set[str]] = {
            "Web Frameworks": set(),
            "AI / Data Science & ML": set(),
            "Databases & ORMs": set(),
            "DevOps & Infrastructure": set(),
            "Other Tools": set()
        }

        # Check filenames first (Docker, CI/CD, etc.)
        lower_files = [f.lower() for f in root_files]
        if any("dockerfile" in f for f in lower_files) or any("docker-compose" in f for f in lower_files):
            detected["DevOps & Infrastructure"].add("Docker")

        # Check Python dependency manifests
        python_manifests = [f for f in root_files if f.lower() in ("requirements.txt", "pyproject.toml", "pipfile", "setup.py")]
        for manifest in python_manifests:
            content = self.client.get_file_content(owner, repo, manifest)
            if content:
                self._match_patterns(content.lower(), detected)

        # Check Node.js / JavaScript manifests
        if "package.json" in root_files:
            content = self.client.get_file_content(owner, repo, "package.json")
            if content:
                try:
                    pkg = json.loads(content)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    joined_deps = " ".join(deps.keys()).lower()
                    self._match_patterns(joined_deps, detected)
                except Exception:
                    self._match_patterns(content.lower(), detected)

        # Check Rust Cargo.toml
        if "Cargo.toml" in root_files:
            content = self.client.get_file_content(owner, repo, "Cargo.toml")
            if content:
                self._match_patterns(content.lower(), detected)

        # Check Go go.mod
        if "go.mod" in root_files:
            content = self.client.get_file_content(owner, repo, "go.mod")
            if content:
                self._match_patterns(content.lower(), detected)

        # Check .github/workflows for GitHub Actions
        workflows = self.client.get_file_content(owner, repo, ".github/workflows")
        # Or check if any file in root points to actions
        if ".github" in root_files:
            detected["DevOps & Infrastructure"].add("GitHub Actions")

        # Convert sets to sorted lists, remove empty categories
        result: Dict[str, List[str]] = {}
        for category, items in detected.items():
            if items:
                result[category] = sorted(list(items))

        return result

    def _match_patterns(self, text: str, detected: Dict[str, Set[str]]):
        for category, framework_map in FRAMEWORK_CATALOG.items():
            for framework_name, patterns in framework_map.items():
                for pat in patterns:
                    if re.search(pat, text, re.IGNORECASE):
                        detected[category].add(framework_name)
                        break
