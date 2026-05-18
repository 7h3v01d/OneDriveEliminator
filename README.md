# OneDrive Eliminator

**Version 2.3 · KeystoneAI · Windows Utility**

A professional, safety-first tool for permanently removing Microsoft OneDrive from Windows. Built with PyQt6, it provides a clean dark UI with live step feedback, a full operation log, and a Dry Run mode so you can see exactly what it will do before committing.

---

## Features

- **8-step removal pipeline** — process termination, account unlinking, app uninstall, Group Policy lock, Explorer namespace cleanup, scheduled task disabling, CLSID shell cleanup, and local file audit
- **Dry Run mode** — simulates all 8 steps and logs what would happen without touching the system; ideal for cautious users or auditing before running on a client machine
- **Live step indicators** — each step shows pending / running / complete / warning / error status in real time
- **Operation log** — timestamped log of every action taken, with a Clear button
- **Safe by design** — never deletes local OneDrive files; cloud files remain intact at onedrive.live.com; warns before any restart
- **Admin elevation** — detects and prompts for administrator rights on launch; displays a banner confirming elevated status
- **Completion flash** — pulsing indicator flashes green on clean completion, red on warnings
- **Run button tracks mode** — button label changes between "Run Elimination", "Run Dry Run", and "Run Again" states so current mode is always clear

---

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or later
- Administrator privileges (required for registry writes and process termination)

---

## Installation

```bash
pip install -r requirements.txt
```

Or directly:

```bash
pip install PyQt6
```

---

## Usage

**Run as Administrator.** Right-click your terminal and choose "Run as administrator", then:

```bash
python OneDriveEliminatorv2.3b.py
```

Or if you have a shortcut or launcher, ensure it is configured to request elevation.

### Recommended workflow

1. Launch as Administrator
2. Enable **Dry Run** and click **Run Dry Run →** to review the operation log
3. Disable **Dry Run** and click **Run Elimination →** to perform the actual removal
4. Restart when prompted

---

## What Each Step Does

| Step | Description |
|---|---|
| Stop Process | Sends `taskkill /F` to terminate `OneDrive.exe` if running |
| Unlink Account | Runs `OneDrive.exe /shutdown` to detach the account cleanly |
| Uninstall App | Runs the native `/uninstall` flag; falls back to `winget` if available |
| Lock Group Policy | Writes `DisableFileSyncNGSC` and `DisableLibrariesDefaultSaveToOneDrive` to `HKLM\SOFTWARE\Policies\Microsoft\Windows\OneDrive`; removes the autorun entry from `HKCU` |
| Clean Explorer | Removes OneDrive CLSID entries from the Explorer Desktop NameSpace keys in both `HKLM` and `HKCU`; hides the entry from Save-As dialogs |
| Disable Tasks | Disables the OneDrive standalone update scheduled tasks via `schtasks` |
| Clean Shell CLSID | Recursively removes ghost CLSID entries from `SOFTWARE\Classes\CLSID` in both hives |
| Audit Local Files | Reports the local OneDrive folder path and file count — **does not delete anything** |

---

## Safety Notes

- **Local files are never deleted.** The tool explicitly audits the local OneDrive folder and reports its contents but takes no action against it.
- **Cloud files are unaffected.** Files synced to OneDrive's cloud storage remain accessible at [onedrive.live.com](https://onedrive.live.com) regardless of what this tool does.
- **Registry changes are write/delete only to OneDrive-specific keys.** No other registry areas are modified.
- **Use Dry Run first** on any machine you are unsure about.

---

## Project Structure

```
OneDriveEliminatorv2.3b.py   — single-file application
requirements.txt              — Python dependencies
README.md                     — this file
```

---

## Changelog

| Version | Changes |
|---|---|
| v2.3b | `paintEvent`-based row rendering — fixes row background width across all DPI/theme configurations |
| v2.3 | Run button label tracks dry run mode; completion flash on `PulsingDot` (green/red hold then fade) |
| v2.2 | Dry Run mode; Clear Log button; status bar resets correctly on Run Again; `dry_run_btn` disables during run |
| v2.1 | Minimize button; `_reset_ui()` on Run Again; `taskkill` returncode fix; `_clean_shell` permission error logging; unused imports removed |
| v2.0 | Initial release — 8-step pipeline, PyQt6 dark UI, admin elevation, threaded worker |

---

## Built by

[KeystoneAI](https://github.com/keystoneai) — local-first AI tools and Windows utilities.
