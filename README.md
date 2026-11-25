Frontend Architecture Advisor
AI-assisted architecture and code-health reviews for TypeScript and Angular applications.

Frontend Architecture Advisor reviews individual TypeScript files or an Angular Git repository and produces a structured report for senior architects and engineering teams. It focuses on clean architecture, separation of concerns, maintainability, lifecycle management, security-sensitive patterns, and practical refactoring priorities.

Repository: vaibhav-vichare/my-agent
What it does
The application provides three ways to run a review:
1. File Upload Review — upload or paste a TypeScript, JavaScript, TSX, or text file for an individual code review.
2. Git Repository Review — provide a Git repository URL or local repository path and a branch to generate an Angular architecture digest for review. Private repositories require valid read credentials.
3. Example Reviews — explore five included Angular-oriented sample scenarios.
The report is organized into five sections:
- Architecture Strengths
- Code Quality
- Architectural Risks
- Critical Blockers
- Refactoring Roadmap
It can also include an overall health verdict, an executive summary, prioritized refactoring actions, an advisory note, and questions to take back to the engineering team. Reports can be downloaded as Markdown.
Review focus
The review guidance and repository scanner focus on patterns such as:
- Angular standalone components and application structure
- Angular signals, computed values, and signal inputs
- Zoneless change-detection readiness and OnPush
- Functional dependency injection with inject()
- Constructor-based dependency injection
- Observable subscriptions and lifecycle cleanup
- TypeScript any usage and type safety
- DomSanitizer bypassSecurityTrust* usage
- Direct localStorage and sessionStorage access
- Angular @defer usage and refactoring opportunities
For repository reviews, the scanner looks for Angular package metadata and examines TypeScript source files. It gathers counts and pattern-based observations that are passed to the review agent. These checks are heuristic source-pattern scans; they are not a TypeScript compiler, full AST analysis, or a substitute for tests, linting, security tooling, or an experienced engineering review.
How it works
At a high level:
1. The Streamlit interface accepts source code, a repository location, or one of the bundled examples.
2. For a Git review, the repository analyzer inspects Angular package metadata and TypeScript files and builds an architecture digest.
3. The agent creates a structured review using either a configured AI model or the built-in demo analyzer.
4. The result is checked for required report sections and consistency, with a model retry when configured AI output fails those checks.
5. The interface presents the findings and makes the report available as a Markdown download.
Demo mode and AI mode
- Demo mode: runs without an API key and uses the built-in rule-based analyzer. It is useful for trying the application, but its findings are limited to the patterns implemented in the demo rules.
- AI mode: when an API key is configured, the application calls an OpenAI-compatible chat-completions endpoint using the configured base URL and model. The AI response is normalized and checked against the report format.
AI-generated recommendations should be reviewed by an engineer and validated against the actual codebase before changes are made.
Technology stack
- Python
- Streamlit
- OpenAI Python SDK (for OpenAI-compatible chat-completions endpoints)
- Pandas
- Git command-line client (for remote repository operations)
Run locally
1. Requirements
- Python 3.10 or later is recommended.
- Git is required for remote Git repository review.
- A supported AI-provider API key is optional; the app can run in demo mode without one.
2. Get the code
git clone https://github.com/vaibhav-vichare/my-agent.git
cd my-agent
Alternatively, download the repository ZIP from GitHub and extract it.
3. Create and activate a virtual environment
macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
Windows PowerShell
py -m venv .venv
.venv\Scripts\Activate.ps1
4. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
5. Start the application
python -m streamlit run app.py
Streamlit will print a local URL (typically http://localhost:8501) in the terminal.
Configure an AI provider (optional)
The app reads configuration from Streamlit secrets first and then from environment variables.

For local use, create .streamlit/secrets.toml using .streamlit/secrets.toml.example as a template. Configure the three values below for your chosen OpenAI-compatible provider:
AI_API_KEY = "your-api-key"
AI_BASE_URL = "https://api.openai.com/v1"
AI_MODEL = "gpt-4o-mini"
Use the base URL and model name required by your provider. The example values above are an OpenAI configuration; other compatible providers may require different values.

Never commit or upload .streamlit/secrets.toml, API keys, or other credentials. The file is excluded by .gitignore. For a hosted deployment, add the same settings through the hosting platform's secrets manager rather than placing them in source code.

Without AI_API_KEY, the app runs in demo mode.
Use the application
Review an individual file
1. Open File Upload Review.
2. Upload a supported source file or paste TypeScript code into the editor.
3. Select Review Code Architecture.
4. Inspect the findings, risks, recommendations, and questions.
Review a Git repository
1. Open Git Repository Review.
2. Choose the sample repository preset or Custom Git Repository.
3. Enter the repository URL or local path and the branch name.
4. For a private repository, provide a valid read-only Personal Access Token or deploy credential in the authentication control.
5. Select Clone & Review Full Architecture.
Only review repositories you are authorized to access. Treat repository credentials as secrets and never include them in a repository URL, source file, screenshot, or commit.
Explore examples
Open Example Reviews, choose one of the included sample scenarios, and select Review This Example Code.
Project structure
my-agent/
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── samples/
│   ├── sample1.ts
│   ├── sample2.ts
│   ├── sample3.ts
│   ├── sample4.ts
│   ├── sample5.ts
│   └── sample_repo/
├── agent.py
├── app.py
├── demo.py
├── git_analyzer.py
├── prompts.py
├── requirements.txt
└── README.md
- app.py — Streamlit user interface and review workflows.
- agent.py — report generation, response normalization, quality checks, and Markdown export.
- prompts.py — system instructions for the Frontend Architecture Advisor.
- git_analyzer.py — Git access, repository scanning, and architecture digest generation.
- demo.py — rule-based demo analyzer used when no AI key is configured.
- samples/ — example TypeScript inputs and a sample repository.
- .streamlit/secrets.toml.example — safe configuration template; copy it locally to secrets.toml and add your own credentials.
Security and privacy notes
- Do not commit .streamlit/secrets.toml, API keys, Personal Access Tokens, or deploy credentials.
- The repository's .gitignore excludes .streamlit/secrets.toml, .env, virtual environments, and Python cache files. Check git status before every commit.
- When reviewing private repositories, use credentials only for repositories you are authorized to access. Use the minimum read permissions required and revoke credentials when they are no longer needed.
- Review the data-handling and retention policies of your AI provider before submitting proprietary source code to an AI endpoint.
- Inspect findings before acting on them. Pattern-based scans can produce incomplete or false-positive observations.
Current scope and limitations
This project is focused on TypeScript and Angular frontend architecture. Its repository scanner uses source-pattern heuristics and extracts a digest; it does not build or execute the target application, run its test suite, perform a complete dependency vulnerability audit, or prove that a codebase is production-ready. The overall verdict is advisory and should be treated as a starting point for engineering review.
Future enhancements
Potential areas for future development include deeper TypeScript parsing, configurable architecture rules, broader framework coverage, richer repository metrics, and automated report comparisons over time.
Author
Vaibhav Vichare

Built as an AI-assisted engineering tool to help frontend architects and engineering teams reason about codebase health and architecture.
If you find an issue or have a suggestion, feel free to open a GitHub issue in this repository.
