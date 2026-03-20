# CapCut Automation Setup

CapCut UI automation on macOS needs Accessibility permission.

## Turn On Accessibility

1. Open `System Settings`
2. Go to `Privacy & Security`
3. Open `Accessibility`
4. Enable access for the app you are using to run me

Usually this will be one of:

- `Codex`
- `Terminal`
- `iTerm`
- `osascript`

If you are not sure, enable both `Codex` and `Terminal`, then try again.

## Quick Test

Run:

```bash
osascript tools/capcut_ui_probe.applescript
```

If permission is correct, it should return the current CapCut window names.

## Next Step

Once Accessibility is enabled, I can continue building:

- open CapCut
- inspect the visible buttons and menus
- locate voice/AI dubbing/voice clone related entry points
- automate the workflow
