# Burp Suite Community

`cento burp` provides local-first wrappers for PortSwigger Burp Suite Community.
It is intended for repeatable setup now and later automation.

## Commands

- `cento burp download`
  Download the latest official Community JAR.
- `cento burp download --type linux`
  Download the latest official Linux installer without running it.
- `cento burp setup`
  Download the Community JAR, copy it into the managed install directory, and
  create `~/.local/bin/burp-community`.
- `cento burp controller start --use-defaults`
  Start Burp in the background and write a PID file.
- `cento burp run`
  Run Burp in the foreground.
- `cento burp stop`
  Stop the background process started by the controller.
- `cento burp restart`
  Restart the background process.
- `cento burp status`
  Print setup and process state.
- `cento burp logs --follow`
  Follow controller output.
- `cento burp paths`
  Print managed paths for scripts.
- `cento burp docs`
  Print embedded workflow documentation.

## Managed Paths

- downloads: `~/.local/share/cento/burp/downloads`
- active JAR: `~/.local/share/cento/burp/current/burpsuite_community.jar`
- launcher: `~/.local/bin/burp-community`
- setup metadata: `~/.local/share/cento/burp/install.env`
- PID file: `~/.local/share/cento/burp/burp.pid`
- log file: `~/.local/share/cento/burp/burp.log`

## Workflow

```bash
cento burp setup
cento burp controller start --use-defaults
cento burp status
cento burp stop
```

The wrapper defaults to the official Community JAR because it is straightforward
to automate and does not require installer UI automation. The Linux installer is
available through `download --type linux` for later manual or scripted installer
work.

Burp Suite is a GUI application. The controller only manages the local Java
process that it starts; it does not configure proxy certificates, browser proxy
settings, or project-specific security workflows.
