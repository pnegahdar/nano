# nano.py

**The models got good enough that the harness doesn't matter anymore.**
**So we made the smallest one that proves it. One file. under 200 lines. Zero dependencies.**

```sh
OPENAI_API_KEY=sk-... ./nano.py "fix the tests"
```

That's the whole thing. No, really.

<p align="center">
  <img src="demo.gif" alt="nano.py finding, running, and fixing tests in one session" width="720" />
</p>

---

### Everything below is in the under 200 lines. We checked.

> 📂 **Reads CLAUDE.md, AGENT.md, AGENTS.md, README.md** — automatic repo context, same files the real agents use
>
> 🧩 **Discovers skill files** — finds SKILL.md from `.claude/skills`, `~/.claude/skills`, `~/.codex/skills`, `~/.codex/plugins`
>
> 🛡️ **Human-in-the-loop approvals** — every command shows what and why before it runs
>
> 🔁 **200-step agentic loop** — keeps going until the job is done, not until it gets bored
>
> 💬 **Interactive REPL** — multi-turn sessions with persistent memory across turns
>
> ⚡ **Non-interactive CLI** — `./nano.py "fix the tests"` and walk away
>
> 🔄 **Session resume** — `./nano.py -c` picks up where you left off, zero local state (OpenAI stores the conversation)

Plus: interactive REPL · one-shot mode · session resume (`-c`) · session picker (`-s`) · GPT-5.5 by default · any model via env var · multi-step tool chaining · approve-one / approve-all / deny · auto-approve mode · per-command cwd, timeout, and env · platform-aware system prompt · output capped at 12KB · forced 5-10 word command descriptions · session reset · zero dependencies · pure stdlib Python · one file you can read in 5 minutes

---

You know that mass of infrastructure behind Claude Code, Codex, Cursor, Devin — the
frameworks, the runtimes, the graphs, the ceremonies, the 200MB node_modules?

Turns out all you actually need is a while loop, one shell tool, and a model that's
not stupid anymore.

`nano.py` is that loop. It sends context to GPT-5.5, lets it run shell commands,
shows you what it wants to do, waits for your approval, and repeats until the job
is done. Pure Python stdlib. Copy it into any repo and go.

The uncomfortable part is how well it works.

## Quick Start

```sh
# Run it straight from GitHub — no install, no clone
OPENAI_API_KEY=sk-... python3 <(curl -s https://raw.githubusercontent.com/pnegahdar/nano/main/nano.py) "fix the tests"

# Or grab it
curl -O https://raw.githubusercontent.com/pnegahdar/nano/main/nano.py && chmod +x nano.py

# One-shot
OPENAI_API_KEY=sk-... ./nano.py "find the bug in auth.py and fix it"

# Interactive REPL
OPENAI_API_KEY=sk-... ./nano.py

# Continue last session in this directory
OPENAI_API_KEY=sk-... ./nano.py -c

# Pick from recent sessions
OPENAI_API_KEY=sk-... ./nano.py -s

# YOLO mode (auto-approve everything, godspeed)
NANO_APPROVE=all OPENAI_API_KEY=sk-... ./nano.py "run the tests and fix whatever breaks"
```

## What It Doesn't Do

- Install 47 packages
- Require a config file
- Need a Docker container
- Have a plugin system
- Use LangChain

## The Architecture

```
while not done:
    response = ask_model(context)
    if response.wants_to_run_command:
        if human_approves(command):
            result = subprocess.run(command)
            context.append(result)
    else:
        print(response)
        done = True
```

That's the architecture diagram. You're welcome.

## Safety

This gives a language model a shell on your computer. You should care about that.

- **Approval is on by default.** Every command shows you what it wants to run and why.
- **You can approve one at a time**, or press `a` to approve all for the session.
- **`NANO_APPROVE=all` skips all prompts.** Only use this when you trust the workspace and the task.
- **Output is capped at 12KB per command** so the model can't filibuster itself.

Read the command before you press `y`. It's under 200 lines — you can audit the whole thing over lunch.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. You know what this is. |
| `OPENAI_MODEL` | `gpt-5.5` | Any model the Responses API supports. |
| `NANO_MAX_STEPS` | `200` | Max tool calls per task before it stops. |
| `NANO_APPROVE` | — | Set to `all` to auto-approve commands. |

## The SWE-bench Question

No score is claimed here. But the shape is right. Same loop every agent runs:
read repo, form hypothesis, run command, observe, repeat.

Wrap it in a harness, give it a budget, collect patches, and find out.

We thought that was funny enough to mention.

## FAQ

**Is this a joke?**<br>
It works. So no. But also a little bit yes.

**Should I use this in production?**<br>
You should not use any autonomous shell agent in production. But you knew that.

**Is under 200 lines a flex?**<br>
It's an observation. We just stopped pretending the harness was the hard part.

**Can I swap in Claude / Gemini / etc?**<br>
The Responses API is OpenAI-specific, but the pattern is universal. Port it in an afternoon.

**Why not just use Claude Code / Codex?**<br>
You should. They're great. This is for the mass of developers who want to understand
what's actually happening inside the black box — and for anyone who looked at a
50,000-line agent framework and mass of configuration and thought *there has to be a simpler way*.

There was.

## License

MIT. Copy it, fork it, vendor it into your monorepo. It's under 200 lines, not a SaaS.

---

<p align="center"><sub>Written by agents, for agents, with agents. The humans just pressed approve.</sub></p>
