# unapicker

FUSE-based file picker for adding graphical file picker support to terminal applications.  Simply give the application `/tmp/picker` and a graphical file picker will launch automatically.

## Install and Quickstart

```bash
pip install unapicker
# install and enable systemd user service
unapicker install_service
```

## Usage

Read from `/tmp/picker` in your application to open a graphical file picker:



## Requirements

- Linux with FUSE support
- Python 3.8+
- One or more file picker applications (zenity, kdialog, etc.)

## Disclaimer

This app was entirely vibe-coded by Claude.