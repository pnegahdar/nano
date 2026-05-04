#!/usr/bin/env python3
import json
import os
import platform
import subprocess
import sys
from urllib.request import Request, urlopen

API = "https://api.openai.com/v1/responses"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
MAX_STEPS = int(os.getenv("NANO_MAX_STEPS", "200"))
APPROVE_ALL = os.getenv("NANO_APPROVE", "").lower() == "all"
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}
_TTY = sys.stderr.isatty()
def _c(code, s): return f"\033[{code}m{s}\033[0m" if _TTY else s

def find_files(roots, names, limit=40):
    home = os.path.expanduser("~")
    found = []
    for root in map(os.path.expanduser, roots):
        if not os.path.isdir(root):
            continue
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in (f for f in files if f.lower() in names):
                path = os.path.abspath(os.path.join(base, name))
                found.append("~" + path[len(home):] if path.startswith(home + os.sep) else os.path.relpath(path))
                if len(found) >= limit:
                    return ", ".join(sorted(dict.fromkeys(found)))
    return ", ".join(sorted(dict.fromkeys(found))) or "none"

def api_key(): return os.getenv("OPENAI_API_KEY") or sys.exit("set OPENAI_API_KEY")

SYSTEM = f"""You are Nano, a general-purpose shell agent with one tool: execute_shell.
Use it to inspect, edit, install, test, search, automate, and answer.
Be concise, tenacious, and relentlessly useful. Keep taking shell steps until done or blocked.
Never run destructive commands unless explicitly requested.
cwd: {os.getcwd()}
platform: {platform.platform()}
python: {sys.version.split()[0]}
shell: {os.getenv("SHELL", "")}
Important docs (read as needed): {find_files([os.getcwd()], {"claude.md", "agent.md", "agents.md", "readme.md"})}
Important skill files (read as needed): {find_files([".claude/skills", "~/.claude/skills", "~/.codex/skills", "~/.codex/plugins"], {"skill.md", "skills.md"})}
"""

TOOL = {
    "type": "function", "name": "execute_shell",
    "description": "Run a shell command with inherited environment.",
    "parameters": {"type": "object", "properties": {
        "command": {"type": "string"},
        "description": {"type": "string", "description": "Why this command is useful right now, in 5-10 words."},
        "cwd": {"type": ["string", "null"]},
        "timeout": {"type": "integer"},
        "env": {"type": "object", "additionalProperties": {"type": "string"}},
    }, "required": ["command", "description"], "additionalProperties": False},
}

def approve(args):
    global APPROVE_ALL
    print(f"\n{_c(90, '# ' + args.get('description', 'No description'))}", file=sys.stderr)
    print(f"{_c(32, '$ ' + args.get('command', ''))}", file=sys.stderr)
    for key in ("cwd", "timeout", "env"):
        if args.get(key) not in (None, "", {}):
            print(f"{_c(90, f'{key}: {args[key]}')}", file=sys.stderr)
    if APPROVE_ALL:
        return True
    try:
        choice = input(f"Approve? {_c(32,'[y] Approve')}  {_c(33,'[a] Approve All')}  {_c(31,'[n] Deny')}: ").strip().lower()
    except EOFError:
        return False
    if choice in ("a", "all"):
        APPROVE_ALL = True
        return True
    return choice in ("y", "yes")

def execute_shell(command, description=None, cwd=None, timeout=60, env=None):
    run_env = {**os.environ, **(env or {})}
    try:
        p = subprocess.run(command, shell=True, cwd=os.path.abspath(cwd or os.getcwd()),
                           env=run_env, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return f"$ {command}\nexit {p.returncode}\n{p.stdout}"[-12000:]
    except subprocess.TimeoutExpired as e:
        return f"$ {command}\ntimeout after {timeout}s\n{e.stdout or ''}"[-12000:]
    except Exception as e:
        return f"{type(e).__name__}: {e}"

def respond(payload, previous=None):
    body = {"model": MODEL, "instructions": SYSTEM, "tools": [TOOL], "input": payload}
    if previous: body["previous_response_id"] = previous
    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}
    with urlopen(Request(API, json.dumps(body).encode(), headers=headers)) as r:
        return json.load(r)

def text(response):
    return "".join(
        part.get("text", "")
        for item in response.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    )

def tool_output(call):
    if call["name"] != "execute_shell":
        result = "unknown tool"
    else:
        try:
            args = json.loads(call.get("arguments") or "{}")
        except json.JSONDecodeError as e:
            result = f"bad arguments: {e}"
        else:
            if not 5 <= len(args.get("description", "").split()) <= 10:
                result = "bad arguments: description must be 5-10 words"
            else:
                result = execute_shell(**args) if approve(args) else _c(31, "denied by user")
    return {"type": "function_call_output", "call_id": call["call_id"], "output": result}

def run(prompt, previous=None):
    response = respond(prompt, previous)
    for _ in range(MAX_STEPS):
        calls = [x for x in response.get("output", []) if x.get("type") == "function_call"]
        if not calls:
            return text(response), response["id"]
        response = respond([tool_output(call) for call in calls], response["id"])
    return "stopped: too many tool calls", response["id"]

def repl():
    previous = None
    print(_c(1, "nano") + " repl " + _c(90, "(:q quit, :reset reset)"))
    while True:
        try:
            prompt = input(f"{_c(1,'nano')}{_c(90,'>')} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if prompt.lower() in (":q", "quit", "exit"):
            return
        if prompt.lower() in (":reset", "reset"):
            previous = None
            print(_c(90, "reset"))
            continue
        if prompt:
            answer, previous = run(prompt, previous)
            print(answer)

if __name__ == "__main__":
    api_key()
    prompt = " ".join(sys.argv[1:])
    print(run(prompt)[0]) if prompt else repl()
