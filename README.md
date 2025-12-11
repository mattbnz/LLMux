# LLMux

OpenAI-compatible proxy for Anthropic Claude Pro/Max, ChatGPT Plus/Pro, and custom OpenAI-compatible providers—all routed through a single endpoint.

## What You Get
- One proxy for Claude, ChatGPT, and any OpenAI-compatible API.
- OAuth logins that mirror the official apps, including 1-year Anthropic tokens.
- Drop-in compatibility with OpenAI client libraries, tools, and SDKs.
- Headless/CI support for automated or containerized deployments.

## Quick Start
1. **Prerequisites:** Python 3.9+, pip, and active provider subscriptions (Claude Pro/Max, ChatGPT Plus/Pro, and/or API keys for custom providers).
2. **Install:**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure (optional):**
   ```bash
   cp .env.example .env
   # Adjust ports, timeouts, etc. as needed
   ```
4. **Run & authenticate:**
   ```bash
   python cli.py
   ```
   - Choose **Authentication** from the menu, sign in for Claude or ChatGPT, then select **Start Proxy Server**.

## Use LLMux
Minimal OpenAI SDK example:
```python
from openai import OpenAI

client = OpenAI(api_key="dummy", base_url="http://localhost:8081/v1")

response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Web Management UI

LLMux includes an optional web-based management interface for remote administration.

### Setup
```bash
cd web
npm install
npm run build
```

The built UI is served automatically at `http://localhost:8081/ui/` when the proxy runs.

### Features
- **Dashboard** – Server status, uptime, and provider health at a glance.
- **Authentication** – Manage Claude and ChatGPT OAuth tokens (login, refresh, logout).
- **API Keys** – Create, rename, and delete proxy API keys.

### Security
The Web UI requires API key authentication. Create a key via the CLI first:
```bash
python cli.py
# → API Keys → Create new key
```
Then use that key to log into the Web UI. Keys are stored in your browser's localStorage.

### Development
For local development with hot reload:
```bash
cd web
npm run dev
```
The dev server proxies API requests to `http://localhost:8081`.

## Documentation Hub
Detailed guides live in `docs/`:
- [`docs/authentication.md`](docs/authentication.md) – OAuth flows, token storage, long-term tokens.
- [`docs/headless.md`](docs/headless.md) – Headless mode, CLI flags, Docker/CI patterns.
- [`docs/configuration.md`](docs/configuration.md) – Environment variables, `.env`, CLI overrides.
- [`docs/models.md`](docs/models.md) – Built-in Claude/GPT models and reasoning variants.
- [`docs/custom-models.md`](docs/custom-models.md) – Adding OpenAI-compatible providers via `models.json`.
- [`docs/client-usage.md`](docs/client-usage.md) – SDK and cURL snippets for common workflows.
- [`docs/reasoning.md`](docs/reasoning.md) – Thinking budgets and reasoning model tips.
- [`docs/web-ui.md`](docs/web-ui.md) – Web Management UI setup and usage.

## Support
<a href="https://buymeacoffee.com/Pimzino" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## Disclaimer
**FOR EDUCATIONAL PURPOSES ONLY.** LLMux is not affiliated with Anthropic or OpenAI, uses undocumented OAuth flows, and may violate provider terms. It can stop working at any time and is provided without warranty. Use official APIs with console-issued keys for production workloads.

## License
MIT License — see [`LICENSE`](LICENSE).
