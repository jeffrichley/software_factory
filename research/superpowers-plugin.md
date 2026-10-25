# How the superpowers plugin is built (template for the Factory plugin)

Research for #6, part of map #1. Question: how is superpowers built (marketplace and install, manifest, the SessionStart hook that injects instructions, how skills/commands/hooks are laid out, how hooks stay cross-platform, how it is versioned and updated), so the **Factory** plugin can copy it? Also: how is Matt Pocock's plugin packaged, since the Factory depends on it.

Sources, all primary:

- **Installed copy** (read only): `~/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/` (git sha `bb92a777`), plus `~/.claude/plugins/{installed_plugins.json,known_marketplaces.json,marketplaces/}`.
- **Upstream**: [obra/superpowers](https://github.com/obra/superpowers) (latest tag `v7.0.1`, 2026-10-21) and [obra/superpowers-marketplace](https://github.com/obra/superpowers-marketplace).
- **Matt Pocock's plugin**: `~/.claude/plugins/cache/mattpocock/mattpocock-skills/1.3.1/`, upstream [mattpocock/skills](https://github.com/mattpocock/skills).
- **Official docs**: [manifest reference](https://code.claude.com/docs/en/plugins-reference), [create a marketplace](https://code.claude.com/docs/en/plugin-marketplaces), [host a marketplace](https://code.claude.com/docs/en/plugins/host-marketplace.md), [plugin loading](https://code.claude.com/docs/en/plugins/loading.md), [plugin dependencies](https://code.claude.com/docs/en/plugins/dependencies.md), [hooks](https://code.claude.com/docs/en/hooks).

## TL;DR

- Superpowers is a **single git repo that is both the plugin and its own marketplace**. The plugin root is the repo root, with `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (`"source": "./"`). Two other marketplaces also list it by git URL.
- It is **skills only** now: `skills/<name>/SKILL.md` plus one `hooks/hooks.json`. It used to ship `commands/` and `agents/` but dropped both.
- The **SessionStart hook** reads `skills/using-superpowers/SKILL.md` and returns it as `hookSpecificOutput.additionalContext`, so every session starts with the bootstrap skill already in context.
- **Cross-platform** comes from three things: `"shell": "bash"` in the hook; a polyglot `run-hook.cmd` that both cmd.exe and bash can run; and hook scripts with no file extension, written in pure bash builtins, kept LF-only by `.gitattributes`.
- **Versioning**: `version` is pinned in `plugin.json`. A `bump-version.sh` script plus `.version-bump.json` keep about 12 manifest files in sync. Users get a new copy only when the version string changes.
- **Matt Pocock's plugin** has the same shape (one repo serving as both plugin and marketplace, `source: "./"`), but it lists its skills explicitly in `plugin.json`, has no hooks, and tags releases as `v1.3.1`.
- **For the Factory**: copy the superpowers layout. Declare `"dependencies": [{"name":"mattpocock-skills","marketplace":"mattpocock"}]` and set `allowCrossMarketplaceDependenciesOn: ["mattpocock"]` in the Factory's marketplace.json.

## 1. Marketplace and install

Superpowers can be installed through three marketplaces (README.md in the installed copy, lines 58–82):

| Marketplace | How the user adds it | How it lists superpowers |
|---|---|---|
| `claude-plugins-official` (Anthropic) | built in | `{"source":"url","url":"https://github.com/obra/superpowers.git","sha":"bb92a777…"}`, pinned to a commit |
| `superpowers-marketplace` (obra) | `/plugin marketplace add obra/superpowers-marketplace` | `{"source":"url","url":"…/superpowers.git"}`, `"strict": true` (plus a `superpowers-dev` entry with `"ref":"dev"`) |
| `superpowers-dev` (the plugin repo itself) | `/plugin marketplace add obra/superpowers` | `.claude-plugin/marketplace.json` with `"source": "./"` |

The user then runs `/plugin install superpowers@<marketplace>`. Claude Code clones the marketplace into `~/.claude/plugins/marketplaces/<name>/`, copies the plugin into `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, and records the install in `installed_plugins.json` along with its scope (user/project/local), `installPath`, `version` and `gitCommitSha`. You can see all of this on this machine. The docs describe the same layout under "Find plugins on disk" in [loading](https://code.claude.com/docs/en/plugins/loading.md).

Because the repo has its own `marketplace.json` with `source: "./"`, **the plugin repo is also an installable marketplace**. One repo is enough to ship a plugin. Matt Pocock does the same thing (§6).

The plugin carries manifests for other agent tools as well (`.cursor-plugin/`, `.codex-plugin/`, `.agents/plugins/marketplace.json`, `gemini-extension.json`, `.opencode/`, `.pi/`, and others). The Factory only needs `.claude-plugin/`.

## 2. Plugin manifest

`.claude-plugin/plugin.json` (7.0.0) holds metadata only and declares no components:

```json
{ "name": "superpowers", "description": "…", "version": "7.0.0",
  "author": {"name": "Jesse Vincent", "email": "…"},
  "homepage": "https://github.com/obra/superpowers",
  "repository": "https://github.com/obra/superpowers",
  "license": "MIT", "keywords": [ … ] }
```

It relies on the default layout. The docs list the defaults as `skills/<name>/SKILL.md`, `commands/`, `agents/`, `hooks/hooks.json`, `.mcp.json`, and `bin/` (put on the Bash PATH). Only `name` is required, and every component is namespaced under it, e.g. `superpowers:brainstorming` ([manifest reference](https://code.claude.com/docs/en/plugins-reference), "Fields" and "Standard layout").

The docs list other manifest fields the Factory may want: `dependencies`, `userConfig`, `defaultEnabled`, `commands` (object map), `mcpServers`, `experimental.monitors`. A `CLAUDE.md` at the plugin root is **not** loaded. Instructions that should load into context have to be skills ("Standard layout").

## 3. The SessionStart hook that injects instructions

`hooks/hooks.json`:

```json
{ "hooks": { "SessionStart": [ { "matcher": "startup|clear|compact",
  "hooks": [ { "type": "command",
    "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" session-start",
    "shell": "bash", "async": false } ] } ] } }
```

`hooks/session-start` is an extensionless bash script. It does four things:

1. Finds the plugin root by splitting `$0` on its last `/` or `\`. It avoids `dirname` because a startup hook can run with an empty PATH (anthropics/claude-code#43127).
2. Reads `skills/using-superpowers/SKILL.md` with the builtin `$(<file)` instead of `cat`, for the same reason.
3. Escapes the text for JSON using `${s//…/…}` substitutions and wraps it in `<EXTREMELY_IMPORTANT>You have superpowers. … </EXTREMELY_IMPORTANT>`.
4. Prints JSON whose shape depends on the host tool: for Claude Code (`CLAUDE_PLUGIN_ROOT` set and no `COPILOT_CLI`/`MUSE_PLUGIN_ROOT`) it is `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"…"}}`. The script comments say it must print **only one** field, because Claude Code reads both `additional_context` and `hookSpecificOutput` without removing duplicates.

The docs confirm the mechanism. SessionStart matchers are `startup`, `resume`, `clear`, `compact` (and `fork`). `hookSpecificOutput.additionalContext` adds context "at the start of the conversation". Plain stdout also counts as context for SessionStart. The docs also say "SessionStart runs on every session, so keep these hooks fast" ([hooks](https://code.claude.com/docs/en/hooks)). Superpowers deliberately leaves `resume` out of its matcher.

On tools with no session-start hook (Antigravity), bootstrap instead relies on the skill's description, "Use when starting any conversation", which gets the model to load the skill (RELEASE-NOTES v7.0.0).

**Factory takeaway:** a SessionStart hook is the right place to inject "you are a Tracked session / here is your Factory context", and to register the session with the dashboard. It should be just as fast and should not depend on PATH.

## 4. How skills, commands and hooks are organised

```
.claude-plugin/{plugin.json, marketplace.json}
skills/<name>/SKILL.md (+ prompt templates, scripts beside it)   # 15 skills
hooks/{hooks.json, hooks-cursor.json, run-hook.cmd, session-start}
scripts/   (bump-version.sh, lint-shell.sh, packaging)
tests/     (shell + node tests per harness)
docs/      (windows/polyglot-hooks.md, porting-to-a-new-harness.md, testing.md)
RELEASE-NOTES.md, .version-bump.json, .gitattributes
```

- **No `commands/` or `agents/`.** The legacy slash commands `/brainstorm`, `/write-plan` and `/execute-plan` were first made user-only (`disable-model-invocation: true`), then deprecated, then removed (#1188). The `agents/code-reviewer.md` persona was folded into a skill-local prompt file (RELEASE-NOTES). Skills are now the only unit.
- Each skill keeps its helper prompts beside `SKILL.md` (e.g. `subagent-driven-development/implementer-prompt.md`).
- The official docs say the same: commands are "Flat Markdown command files. Prefer `skills/` for new plugins."
- **Implication for the Factory's slash commands (launching Jobs):** write them as skills with `disable-model-invocation: true`. They show up as `/factory:<name>`, and Claude cannot fire them on its own. Matt Pocock's `wayfinder`, `implement` and `implement-spec` already carry `disable-model-invocation: true`, so only the user, or a prompt that starts with the slash command, can start them. Claude cannot call them through the Skill tool. A Factory Job therefore has to launch them as a typed slash command (e.g. as the prompt of a new `claude` session), not ask the model to invoke them.

## 5. Cross-platform hooks (WSL, Windows PowerShell, macOS)

Documented in `docs/windows/polyglot-hooks.md` (which says to trust the code when it disagrees). The pieces:

1. **`"shell": "bash"`** on the hook. The docs say `shell` accepts `"bash"` or `"powershell"` and defaults to bash, or to PowerShell on Windows when Git Bash is not installed ([hooks](https://code.claude.com/docs/en/hooks), "Command hook fields"). Superpowers sets bash so that PowerShell/CMD never try to parse the quoted-path command. When Git Bash is missing, the user gets an actionable error instead of a parser failure. The field needs Claude Code 2.1.81+ (older versions ignore it).
2. **Polyglot `run-hook.cmd`.** It starts with `: << 'CMDBLOCK'`, so bash sees a no-op heredoc and cmd.exe sees a batch file.
   - The cmd half looks for `bash.exe` in Program Files Git, then Program Files (x86), then `%LOCALAPPDATA%\Programs\Git`, then `where.exe $PATH:bash`. It calls `where` by full path and skips the WSL launchers in System32, Sysnative and WindowsApps. It then runs `bash <hookdir>\<script>` and returns the script's exit code. If no bash is found it **exits 0 silently**, so the plugin still works without the bootstrap.
   - The bash half `exec "${BASH:-bash}" "$SCRIPT_DIR/$1"`.
3. **Extensionless hook scripts** (`session-start`, not `session-start.sh`). Claude Code on Windows puts `bash` in front of any command containing `.sh`, which used to break the wrapper (RELEASE-NOTES; anthropics/claude-code#9758, #3417).
4. **Pure-bash, PATH-independent scripts**: no `dirname`/`cat`; JSON escaping done in bash; `printf` instead of heredoc (bash 5.3 heredoc hang, obra/superpowers#571); output piped through `cat` only if `cat` exists, to absorb EPIPE on Git Bash (#1612).
5. **`.gitattributes`** forces `eol=lf` on `*.sh`, `hooks/session-start` and `*.cmd`, so a Windows checkout cannot corrupt the polyglot file.
6. `${CLAUDE_PLUGIN_ROOT}` is quoted because the path may contain spaces. The docs add that on Windows most substituted paths use forward slashes (`C:/Users/…`) ([manifest reference](https://code.claude.com/docs/en/plugins-reference), "Quoting and path separators").

WSL and macOS go straight to the bash half. Native Windows needs Git for Windows; without it the hook is skipped. **Factory caveat:** the Factory's hooks are core functionality (dashboard state, Needs you / Done), not optional context. Silently skipping them is not acceptable for the Factory. It will need either a hard requirement on Git Bash or a `"shell": "powershell"` variant for native Windows. Hooks will also need a runtime the dashboard can be talked to from (e.g. node, which Claude Code itself ships with). This is open for the Factory spec.

## 6. Versioning and updates

**Superpowers:**

- `version` is pinned in `plugin.json` (and in its own `marketplace.json` entry). `.version-bump.json` lists about 12 files and JSON paths to keep in sync (`package.json`, every `*-plugin/plugin.json`, `marketplace.json` `plugins.0.version`, `gemini-extension.json`). `scripts/bump-version.sh <ver> | --check | --audit` rewrites them with `jq`/`yq` and detects drift. Releases are git tags `vX.Y.Z` with GitHub releases and a hand-written `RELEASE-NOTES.md`.
- Anthropic's official marketplace pins superpowers to a commit `sha`, so official users get a release only when Anthropic bumps the sha. On this machine 7.0.0 is installed, while upstream is already at v7.0.1.

**Claude Code rules** ([loading](https://code.claude.com/docs/en/plugins/loading.md), "Versions and updates"; [host](https://code.claude.com/docs/en/plugins/host-marketplace.md), "Keep users up to date"):

- **How the version is computed**: the `plugin.json` `version` wins, then the marketplace entry's `version`, then the git commit SHA (12 chars) for git sources. The computed version names the cache dir and is the only signal that an update exists. If you pin `version` and push commits without bumping it, users get nothing. If you omit `version` everywhere, users track every commit. Don't set it in both places.
- **Auto-update** is on by default only for Anthropic's official marketplaces and **off for every other marketplace**. The user enables it in `/plugin` → Marketplaces, or an admin sets `extraKnownMarketplaces.<m>.autoUpdate`. Otherwise updates happen through `/plugin marketplace update` or `claude plugin update`. The update runs in the background after the first message, and new versions load after `/reload-plugins` or a restart. On this machine no marketplace has `autoUpdate` set.
- Old version dirs get an `.orphaned_at` marker and are deleted 14 days later. `${CLAUDE_PLUGIN_ROOT}` changes with every version, so durable state (such as the Factory's dashboard DB or session registry) belongs in `${CLAUDE_PLUGIN_DATA}` = `~/.claude/plugins/data/<id>/`, which survives updates.
- A `package.json` plus lockfile at the plugin root gets an automatic `npm`/`bun` install of registry deps into the cache copy (no lifecycle scripts, 60 s timeout). This is relevant if the Factory dashboard is a node app.
- Per-repo opt-in: `claude plugin marketplace add … --scope project` writes `extraKnownMarketplaces` to the repo's `.claude/settings.json`, and `enabledPlugins` there turns the plugin on for anyone who trusts the folder. A plugin enabled only in project settings is **not fetched** onto a machine where it isn't already installed, unless it uses a relative-path source.

## 7. How Matt Pocock's plugin is packaged

- Marketplace `mattpocock`, added as `{"source":"git","url":"https://github.com/mattpocock/skills.git"}` (`known_marketplaces.json`). The repo root holds `.claude-plugin/marketplace.json`, which has one entry `mattpocock-skills` with `"source": "./"`. Same pattern as superpowers. Install id: `mattpocock-skills@mattpocock`, cached at `cache/mattpocock/mattpocock-skills/1.3.1/`.
- `plugin.json` pins `"version": "1.3.1"` and has an **explicit `skills` array** of 27 paths such as `./skills/engineering/wayfinder` and `./skills/productivity/grilling`. The repo nests skills by category (`engineering/`, `productivity/`, `misc/`, `in-progress/`, `deprecated/`), so only the listed ones ship. `misc/` and `in-progress/` skills are not exposed.
- No hooks, commands, agents or MCP. Skills only. Some skills are user-only (`disable-model-invocation: true`: `wayfinder`, `implement`, `implement-spec`, and others).
- Versions are managed with Changesets (`package.json` script `changeset version && node scripts/sync-plugin-version.mjs`), with git tags `v1.3.1`, `v1.3.0`, …
- The mattpocock marketplace is not official, so **auto-update is off** unless the user turns it on.

## 8. Depending on Matt Pocock's plugin from the Factory

From [plugin dependencies](https://code.claude.com/docs/en/plugins/dependencies.md):

- In the Factory's `plugin.json`: `"dependencies": [{ "name": "mattpocock-skills", "marketplace": "mattpocock" }]` (or the string `"mattpocock-skills@mattpocock"`).
- Cross-marketplace dependencies are **blocked by default**. The Factory's own `marketplace.json` must set `"allowCrossMarketplaceDependenciesOn": ["mattpocock"]`. Otherwise a dependency declared in `plugin.json` silently doesn't install and the Factory then fails to load. The check is skipped if the user already has `mattpocock-skills@mattpocock` enabled at the same scope.
- **Version ranges** resolve against git tags named `<plugin>--v<version>`. Matt tags `v1.3.1`, not `mattpocock-skills--v1.3.1`. Because his entry is a relative-path (`./`) source, a range such as `^1.3` falls back to "the marketplace's current copy" and is only *checked at load* (out of range → Factory disabled). Prefer **no constraint**, so the Factory tracks his latest release, which fits the "adopt new releases" constraint in #1. Dependency installs also run on `/reload-plugins`, auto-update and `marketplace add`.
- **Unverified:** whether Claude Code adds the `mattpocock` marketplace itself when the user has never added it. The docs speak only of "resolve `name` in" that marketplace. The safe install instructions are: add both marketplaces, then install the Factory. The Factory install command can check for this.
- `--plugin-dir ./factory --plugin-dir <matt>` satisfies the dependency during local development.

## Recommended Factory skeleton (derived)

```
software_factory/                      # one repo = plugin + its marketplace
  .claude-plugin/plugin.json           # name "factory"(?), version, dependencies: mattpocock-skills@mattpocock
  .claude-plugin/marketplace.json      # source "./", allowCrossMarketplaceDependenciesOn ["mattpocock"]
  skills/<name>/SKILL.md               # Factory slash commands as user-only skills
  hooks/hooks.json                     # SessionStart / Notification / Stop / etc., "shell": "bash"
  hooks/run-hook.cmd + extensionless scripts   # superpowers polyglot pattern
  .gitattributes                       # eol=lf for hooks
  scripts/bump-version.sh (or changesets)
```

State lives in `${CLAUDE_PLUGIN_DATA}`. Bump `version` on every release, or omit it and track commits. Tell users to turn on auto-update for the Factory marketplace and for `mattpocock`.

Naming: the name must not start with `claude-`/`anthropic-`. `factory` is fine.
