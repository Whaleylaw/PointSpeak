# Agent adapters

PointSpeak bundles are local folders, so agents do not need a special SDK to use them. The receiver can prepare a generic adapter payload for any CLI or desktop agent that can read files from disk.

## Generic CLI adapter

The generic adapter writes two files into each session bundle:

```text
handoff/generic-agent-prompt.md
handoff/generic-agent-adapter.json
```

It also writes agent-specific copies under:

```text
handoff/adapters/<agent>.prompt.md
handoff/adapters/<agent>.adapter.json
```

The prompt is self-contained and points the agent at the bundle, intake JSON, replay HTML, privacy report, and handoff markdown.

## Generate an adapter for an existing session

```bash
curl 'http://127.0.0.1:48321/sessions/<session-id>/agent-adapter?agent=claude-code'
```

To get only the prompt text:

```bash
curl 'http://127.0.0.1:48321/sessions/<session-id>/agent-prompt.md?agent=codex'
```

## Use with Claude Code

```bash
claude < ~/.pointspeak/sessions/<session-id>/session.pointspeak/handoff/adapters/claude-code.prompt.md
```

## Use with Codex

```bash
codex exec < ~/.pointspeak/sessions/<session-id>/session.pointspeak/handoff/adapters/codex.prompt.md
```

Exact command-line flags vary by agent version. The stable contract is the generated prompt file and the bundle paths it references.

## Bridge mode

A bridge lease can use the generic adapter instead of delivering to a Hermes API server:

```json
{
  "agent": "codex",
  "ttlMinutes": 120,
  "bridgeMode": "generic_cli",
  "wakeChat": false
}
```

When a session is finalized, PointSpeak prepares the generic adapter files and records a bridge event with delivery status `prepared`. Another process, watcher, or user can then feed the prompt into Claude Code, Codex, or another local agent.

## Privacy

The generic adapter does not upload files. It only writes local prompt and JSON files. Agents that consume the prompt may still read screenshots and page metadata from disk, so review `privacy-report.json` before sending captures to untrusted systems.
