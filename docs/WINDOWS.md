# Windows

Architecture Practice supports 64-bit Windows 10 and Windows 11.

## Run the packaged app

Download and extract the Windows x64 release, then double-click `ArchitecturePractice.exe`. Python is not required. The app opens its local page in your default browser and listens only on `127.0.0.1`. Keep the extracted application files together; do not move individual files out of the release folder.

If Windows shows a Microsoft Defender SmartScreen notice because the release is unsigned, check that you obtained the file from the project's trusted release page. If you trust that source, use Windows' normal **More info** and **Run anyway** choice for this app. Do not turn off SmartScreen or other Windows protections. Releases are not promised to be signed.

Your history and server log are stored per Windows user under `%LOCALAPPDATA%\ArchitecturePractice` (normally `C:\Users\<you>\AppData\Local\ArchitecturePractice`). The app needs write access there. Keep that folder if you want to preserve your history; back it up along with any browser export you choose to keep.

## Run from source

Install Python 3.10 or newer, then extract or clone the source and double-click `Start-Windows.bat`. The launcher checks for Python and starts the app without requiring third-party Python packages. If Windows cannot find Python, install it from [python.org](https://www.python.org/downloads/windows/) and select **Add Python to PATH**, then try again.

Alternatively, open Command Prompt in the project folder and run:

```bat
py -3 -B launcher.py
```

To choose a different local port, pass `--port`, for example `py -3 -B launcher.py --port 9123`. The same port must be available to the app. If it is occupied by another program, the launcher reports the conflict and leaves that program alone.

The regular launcher leaves the local server running after it opens the browser. To run it in the foreground and stop it with Ctrl+C, use `py -3 -B launcher.py --serve` (add `--port 9123` to choose a port). To stop a server started by double-clicking the app, use Task Manager to end that `ArchitecturePractice.exe` process.

## Optional local AI adapter

The app works without an AI adapter. To use AI review, configure the compatible local adapter as described in the main README. By default, the key file is `%LOCALAPPDATA%\ArchitecturePractice\adapter-key`. Keep the key in a local file; do not put it in the release folder, source control, or screenshots. Windows users can set `TRAINER_ADAPTER_KEY_FILE` to another key file path and `TRAINER_ADAPTER_URL` to the adapter's loopback address in their environment before starting the app. The adapter URL must remain on the local computer.

The app stores user data separately from the packaged application files so Windows does not need to grant write access to the install or extraction folder. Do not expose the local server through a public network address or tunnel.
