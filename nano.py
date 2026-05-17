#!/usr/bin/env python3
import json, os, platform, subprocess, sys, threading, time
from urllib.request import Request, urlopen

try:
    import readline
except ImportError:
    pass
else:
    readline.parse_and_bind("\\C-l: clear-screen")
API = "https://api.openai.com/v1/responses"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
MAX_STEPS = int(os.getenv("NANO_MAX_STEPS", "200"))
APPROVE_ALL = os.getenv("NANO_APPROVE", "").lower() == "all"
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}
SESSIONS = os.path.expanduser("~/.nano_sessions.json")
CWD = os.getcwd()
_TTY = sys.stderr.isatty()
def _color(code, text): return f"\033[{code}m{text}\033[0m" if _TTY else text
def _spinner(done, frames="-\\|/"):
    index = 0
    while not done.wait(0.1):
        print(f"\r  {_color(90, frames[index % len(frames)] + ' thinking')}", end="", file=sys.stderr, flush=True)
        index += 1
    print("\r             \r", end="", file=sys.stderr, flush=True)

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
Output short plain-text snippets optimized for terminal reading; no markdown rendering or syntax highlighting.
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
    print(f"\n{_color(90, '# ' + args.get('description', 'No description'))}", file=sys.stderr)
    print(f"{_color(32, '$ ' + args.get('command', ''))}", file=sys.stderr)
    for key in ("cwd", "timeout", "env"):
        if args.get(key) not in (None, "", {}):
            print(f"{_color(90, f'{key}: {args[key]}')}", file=sys.stderr)
    if APPROVE_ALL: return True
    try:
        choice = input(f"Approve? {_color(32,'[y] Approve')}  {_color(33,'[a] Approve All')}  {_color(31,'[n] Deny')}: ").strip().lower()
    except EOFError: return False
    if choice in ("a", "all"):
        APPROVE_ALL = True; return True
    return choice in ("y", "yes")

def execute_shell(command, description=None, cwd=None, timeout=60, env=None):
    run_env = {**os.environ, **(env or {})}
    try:
        process = subprocess.run(command, shell=True, cwd=os.path.abspath(cwd or os.getcwd()),
                                 env=run_env, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=timeout)
        return f"$ {command}\nexit {process.returncode}\n{process.stdout}"[-12000:]
    except subprocess.TimeoutExpired as error:
        return f"$ {command}\ntimeout after {timeout}s\n{error.stdout or ''}"[-12000:]
    except Exception as error:
        return f"{type(error).__name__}: {error}"

def respond(payload, previous=None):
    body = {"model": MODEL, "instructions": SYSTEM, "tools": [TOOL], "input": payload}
    if previous: body["previous_response_id"] = previous
    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}
    spinner_done = threading.Event() if _TTY else None
    spinner_thread = threading.Thread(target=_spinner, args=(spinner_done,), daemon=True) if spinner_done else None
    if spinner_thread: spinner_thread.start()
    try:
        with urlopen(Request(API, json.dumps(body).encode(), headers=headers)) as api_response:
            return json.load(api_response)
    finally:
        if spinner_thread: spinner_done.set(); spinner_thread.join()

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
        except json.JSONDecodeError as error:
            result = f"bad arguments: {error}"
        else:
            if not 5 <= len(args.get("description", "").split()) <= 10:
                result = "bad arguments: description must be 5-10 words"
            else:
                result = execute_shell(**args) if approve(args) else _color(31, "denied by user")
    return {"type": "function_call_output", "call_id": call["call_id"], "output": result}

def run(prompt, previous=None):
    response = respond(prompt, previous)
    for _ in range(MAX_STEPS):
        calls = [x for x in response.get("output", []) if x.get("type") == "function_call"]
        if not calls:
            return text(response), response["id"]
        response = respond([tool_output(call) for call in calls], response["id"])
    return "stopped: too many tool calls", response["id"]

def load_sessions():
    try: return json.load(open(SESSIONS))
    except (FileNotFoundError, json.JSONDecodeError): return []

def save_session(response_id, label):
    sessions = load_sessions()
    sessions = [session for session in sessions if not (session["label"] == label and session["cwd"] == CWD)]
    sessions.append({"id": response_id, "label": label[:80], "cwd": CWD, "ts": int(time.time())})
    json.dump(sessions[-50:], open(SESSIONS, "w"))

def pick_session():
    sessions = [session for session in load_sessions() if session["cwd"] == CWD][-10:]
    if not sessions: sys.exit("no sessions in this directory")
    for index, session in enumerate(reversed(sessions)):
        age = int(time.time()) - session["ts"]
        label = f"{age//60}m" if age < 3600 else f"{age//3600}h" if age < 86400 else f"{age//86400}d"
        print(f"  {_color(90, str(index))}  {session['label']}  {_color(90, label + ' ago')}")
    try: choice = input(f"{_color(1,'nano')}{_color(90,'#')} ").strip()
    except (EOFError, KeyboardInterrupt): print(); sys.exit(0)
    try: return sessions[-(int(choice) + 1)]
    except (ValueError, IndexError): sys.exit("invalid session")

def repl(previous=None, label=None):
    print(_color(1, "nano") + " repl " + _color(90, "(:q quit, :reset reset)"))
    while True:
        try:
            prompt = input(_color(36, "nano > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print(); return
        if not prompt: continue
        if prompt.lower() in (":q", "quit", "exit"): return
        if prompt.lower() in (":reset", "reset"):
            previous, label = None, None
            print(_color(90, "reset")); continue
        answer, previous = run(prompt, previous)
        if not label: label = prompt
        save_session(previous, label)
        print(answer)
if __name__ == "__main__":
    api_key()
    args = sys.argv[1:]
    flag = args.pop(0) if args and args[0] in ("-c", "-s") else None
    prompt = " ".join(args)
    previous, label = None, None
    if flag == "-s":
        session = pick_session()
        previous, label = session["id"], session["label"]
        print(_color(90, f"resuming: {label}"))
    elif flag == "-c":
        sessions = [session for session in load_sessions() if session["cwd"] == CWD]
        if not sessions: sys.exit("no sessions in this directory")
        previous, label = sessions[-1]["id"], sessions[-1]["label"]
        print(_color(90, f"continuing: {label}"))
    if prompt:
        answer, response_id = run(prompt, previous)
        save_session(response_id, label or prompt)
        print(answer)
    else:
        repl(previous, label)
