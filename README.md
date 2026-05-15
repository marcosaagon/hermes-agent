# Hermes Agent

A fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — an autonomous AI agent framework powered by Hermes models with tool-use and function-calling capabilities.

## Features

- 🤖 **Hermes Model Integration** — Optimized for NousResearch Hermes series models
- 🛠️ **Tool Use & Function Calling** — Native support for structured tool invocation
- 🔄 **Agentic Loops** — Multi-step reasoning and task execution
- 🐳 **Docker Support** — Containerized deployment ready
- 🔧 **Configurable** — Extensive environment-based configuration

## Quick Start

### Prerequisites

- Python 3.10+
- An OpenAI-compatible API endpoint (e.g., vLLM, Ollama, OpenAI)
- Docker (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/hermes-agent
cd hermes-agent

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings
```

### Configuration

Copy `.env.example` to `.env` and configure the required variables:

```bash
# Required
OPENAI_API_BASE=http://localhost:8000/v1
OPENAI_API_KEY=your-api-key
MODEL_NAME=NousResearch/Hermes-3-Llama-3.1-8B
```

### Running

```bash
# Run directly
python main.py

# Or with Docker
docker compose up
```

## Usage

```python
from hermes_agent import HermesAgent

agent = HermesAgent(
    model="NousResearch/Hermes-3-Llama-3.1-8B",
    tools=[...],  # your tool definitions
)

response = agent.run("Search the web for the latest AI news and summarize it.")
print(response)
```

## Architecture

```
hermes-agent/
├── hermes_agent/        # Core agent library
│   ├── agent.py         # Main agent loop
│   ├── tools/           # Built-in tool implementations
│   ├── models/          # Model interface & prompting
│   └── utils/           # Shared utilities
├── tools/               # Additional tool definitions
├── tests/               # Test suite
├── docker-compose.yml   # Docker Compose configuration
└── main.py              # Entry point
```

## Tools

Hermes Agent comes with several built-in tools:

| Tool | Description |
|------|-------------|
| `web_search` | Search the web using configured search API |
| `code_interpreter` | Execute Python code in a sandboxed environment |
| `file_read` | Read files from the local filesystem |
| `file_write` | Write files to the local filesystem |
| `http_request` | Make HTTP requests to external APIs |

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Lint
ruff check .

# Format
ruff format .
```

## Contributing

Contributions are welcome! Please open an issue or pull request.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgements

- [NousResearch](https://nousresearch.com/) for the original hermes-agent and Hermes model series
- The open-source AI community
