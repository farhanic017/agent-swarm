# Contributing to Agent Swarm

Thanks for helping improve Agent Swarm. The fastest way to make the project more useful is to contribute tested agent capabilities, provider integrations, workflow examples, and documentation that helps developers run real multi-agent systems.

## Good First Contributions

- Add or improve an example in `examples/`.
- Add tests for an existing agent, provider, or tool.
- Improve provider setup docs for OpenAI, Anthropic, Azure OpenAI, OpenRouter, Google, Kimi, Hugging Face, or ElevenLabs.
- Add a small, scoped agent capability with tests.
- Improve benchmark dashboards or demo assets.

## Development Setup

```bash
git clone https://github.com/farhanic017/agent-swarm.git
cd agent-swarm
pip install -r requirements.txt
python -m pytest -q
```

## Pull Request Checklist

- Keep changes focused on one feature, fix, or doc improvement.
- Add or update tests when behavior changes.
- Do not commit API keys, `.env` files, generated private state, or local credentials.
- Run `python -m pytest -q` before opening a pull request.
- Explain what changed, why it matters, and how you verified it.

## Issue Tips

When opening an issue, include:

- Your Python version and operating system.
- The command you ran.
- The expected result.
- The actual result or traceback.
- Any relevant provider configuration, without secrets.
