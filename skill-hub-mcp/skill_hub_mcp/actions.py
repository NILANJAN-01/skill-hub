"""Install, update and remove skills through the hub's own installer (tools/install.py).

The installer stays the single source of truth for agent folders and planning. This module only
drives it: `plan` is always read-only and returns a token; `apply` runs exactly that plan and is
only possible when the server was started with --allow-install. Standard library only.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from .hub import HubError

TOKEN_SECONDS = 600
ACTIONS = ("install", "update", "remove")


class Actions:
    def __init__(self, hub, allow_write=False):
        self.hub, self.allow_write = hub, allow_write
        self._module, self._root, self._pending = None, None, {}

    # ---- the installer module and a hub folder on disk
    def _run(self, fn, *args, **kwargs):
        """Call installer code: keep its prints off stdout (the protocol channel) and turn its exits into errors."""
        log = io.StringIO()
        try:
            with contextlib.redirect_stdout(log):
                result = fn(*args, **kwargs)
        except SystemExit as exc:
            raise HubError(str(exc.code) if exc.code not in (None, 0) else "the installer stopped") from None
        except OSError as exc:
            raise HubError(f"file error: {exc}") from None
        return result, log.getvalue().strip()

    def module(self):
        if self._module is None:
            source = self.hub.source
            if source.kind == "local":
                path = source.root / "tools" / "install.py"
                if not path.is_file():
                    raise HubError(f"{source.root} has no tools/install.py")
            else:
                path = Path(tempfile.mkdtemp(prefix="skill-hub-mcp-")) / "install.py"
                path.write_bytes(source.raw("tools/install.py"))
            spec = importlib.util.spec_from_file_location("skill_hub_installer", str(path))
            module = importlib.util.module_from_spec(spec)
            self._run(spec.loader.exec_module, module)
            self._module = module
        return self._module

    def root(self):
        """A folder holding the hub's skills: the local clone, or a download of the remote ref."""
        if self._root is None:
            source = self.hub.source
            if source.kind == "local":
                self._root = source.root
            else:
                mod = self.module()
                mod.REPO = source.repo
                self._root, _ = self._run(mod.download_hub, source.ref)
        return self._root

    # ---- arguments
    def _agents(self, agents):
        mod = self.module()
        if not agents or agents.strip() == "detected":
            found = list(mod.detect_agents())
            if not found:
                raise HubError("no supported agent was detected on this machine. Pass agents explicitly, "
                               f"for example 'claude-code'. Known: {', '.join(mod.AGENTS)}")
            return found
        chosen = list(dict.fromkeys(a.strip() for a in agents.split(",") if a.strip()))
        unknown = [a for a in chosen if a not in mod.AGENTS]
        if unknown:
            raise HubError(f"unknown agent(s): {', '.join(unknown)}. Known: {', '.join(mod.AGENTS)}, detected")
        return chosen

    def _where(self, scope, project, agents):
        mod = self.module()
        if scope == "user":
            usable = [a for a in agents if mod.AGENTS[a]["global"]]
            if not usable:
                raise HubError("none of the chosen agents has a user-level skills folder; use scope 'project'")
            return True, Path.cwd(), usable
        if not project:
            raise HubError("scope 'project' needs 'project': the absolute path of the project folder")
        path = Path(project).expanduser()
        if not path.is_absolute() or not path.is_dir():
            raise HubError(f"project must be an existing folder given as an absolute path: {project}")
        return False, path.resolve(), agents

    # ---- read-only tools
    def detect(self):
        mod = self.module()
        found = mod.detect_agents()
        return {"detected": [{"id": k, "name": mod.AGENTS[k]["name"], "evidence": ev[:2]} for k, ev in found.items()],
                "not_detected": [k for k in mod.AGENTS if k not in found and k != "universal"]}

    def installed(self, agents=None, scope="user", project=None):
        mod, root = self.module(), self.root()
        chosen = self._agents(agents)
        use_global, proj, chosen = self._where(scope, project, chosen)
        known = set(mod.all_skills(root))
        read_manifest = getattr(mod, "read_manifest", lambda folder: {"skills": {}})
        folders, total = [], 0
        for folder in dict.fromkeys(f for a in chosen for f in mod.reads(a, use_global, proj)):
            versions = read_manifest(folder)["skills"]
            rows = [{"skill": s, "version": versions.get(s, {}).get("version", "unknown"),
                     "matches_hub": mod.same_skill(root / "skills" / s, folder / s)}
                    for s in sorted(known) if (folder / s / "SKILL.md").is_file()]
            if rows:
                folders.append({"folder": str(folder), "skills": rows})
                total += len(rows)
        return {"agents": chosen, "scope": scope, "hub_version": self.hub.version, "installed": total,
                "folders": folders}

    def plan(self, action, target, agents=None, scope="user", project=None):
        if action not in ACTIONS:
            raise HubError(f"action must be one of: {', '.join(ACTIONS)}")
        mod, root = self.module(), self.root()
        plugins, skills = self.hub.targets(target)
        names, _ = self._run(mod.resolve, root, plugins, skills)
        chosen = self._agents(agents)
        use_global, proj, chosen = self._where(scope, project, chosen)
        steps = []
        if action == "remove":
            folders = dict.fromkeys(f for a in chosen for f in mod.reads(a, use_global, proj))
            work = [(f, s) for f in folders for s in names if (f / s / "SKILL.md").is_file()]
            steps = [{"do": "remove", "skill": s, "folder": str(f)} for f, s in work]
            payload = ("remove", work)
        else:
            plan = mod.make_plan(root, names, chosen, use_global, proj)
            for folder, items in plan["install"].items():
                steps += [{"do": "install", "skill": s, "folder": str(folder)} for s in items]
            for folder, items in plan["outdated"].items():
                steps += [{"do": "update" if action == "update" else "skip (differs from the hub; use action 'update')",
                           "skill": s, "folder": str(folder)} for s in items]
            if action == "install":
                plan = dict(plan, outdated={})
            plan = dict(plan, redundant={})          # never delete as a side effect of installing
            payload = ("install", plan)
        changes = [s for s in steps if s["do"] in ACTIONS]
        command = "python tools/install.py --agent " + ",".join(chosen) + \
                  "".join(f" --plugin {p}" for p in plugins) + "".join(f" --skill {s}" for s in skills) + \
                  (" --global" if use_global else f' --project "{proj}"') + \
                  {"install": "", "update": " --update", "remove": " --remove"}[action]
        out = {"action": action, "agents": chosen, "scope": scope, "skills": len(names), "changes": len(changes),
               "steps": steps, "equivalent_command": command + "   # run inside a clone of the hub"}
        if not changes:
            out["next"] = "Nothing to change."
            return out
        if not self.allow_write:
            out["next"] = ("This server is read-only. Show the user the steps and the equivalent command to run "
                           "themselves, or restart the server with --allow-install.")
            return out
        self._pending = {t: p for t, p in self._pending.items() if p["expires"] > time.time()}
        token = secrets.token_hex(8)
        self._pending[token] = {"payload": payload, "root": root, "expires": time.time() + TOKEN_SECONDS,
                                "changes": len(changes)}
        out["token"] = token
        out["next"] = ("Show these steps to the user. Only after the user agrees, call apply_change with this token. "
                       f"The token expires in {TOKEN_SECONDS // 60} minutes.")
        return out

    # ---- the only tool that writes
    def apply(self, token):
        if not self.allow_write:
            raise HubError("this server is read-only; restart it with --allow-install to let it change files")
        pending = self._pending.pop(token, None)
        if pending is None or pending["expires"] < time.time():
            raise HubError("unknown or expired token. Call plan_change again and show the new plan to the user.")
        mod, (kind, work) = self.module(), pending["payload"]
        record = getattr(mod, "record", None)
        if kind == "remove":
            def remove():
                for folder, skill in work:
                    if (folder / skill / "SKILL.md").is_file():
                        shutil.rmtree(folder / skill)
                        if record:
                            record(folder, skill, None)
                        print(f"removed {folder / skill}")
                return len(work)
            done, log = self._run(remove)
        else:
            done, log = self._run(mod.apply_plan, pending["root"], work, True, False, False)
        return {"done": done, "log": log.splitlines(),
                "next": "Tell the user to restart or reload their agent so it picks up the change."}
