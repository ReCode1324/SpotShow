
# SpotShow

**SpotShow** is a lightweight, open-source desktop app for browsing, searching, and organizing metadata from your locally available SpotPlayer course library.

It helps you find courses, lessons, and downloaded `.spot` files without changing the original database or replacing SpotPlayer's official playback engine.

## ✨ Features

- **Unified course browser** — Explore downloaded courses and nested lessons in one interface.
- **Fast local search** — Find courses, topics, and lessons in your local catalog.
- **Downloaded asset locator** — See where `.spot` files are stored on your computer.
- **Read-only metadata access** — Browse course information without modifying the SpotPlayer database.
- **Standard media playback** — Play supported, unprotected media files directly in SpotShow.
- **Official SpotPlayer hand-off** — Open protected `.spot` content using your installed copy of SpotPlayer.

## 🔒 Privacy & Security

SpotShow is designed to work locally and respect your existing media library:

- **Local-first:** No SpotShow telemetry, tracking, or application-managed external API requests.
- **No credential access:** Reads structural metadata such as titles, paths, and lesson indices—not license keys, session credentials, encrypted secrets, or DRM materials.
- **Non-destructive:** Does not alter the original SpotPlayer database or protected media files.
- **No DRM bypass:** Protected content remains under the control of the official SpotPlayer application.

> **Note:** When SpotShow hands a file off to SpotPlayer, the official player may use its own network services or authentication. SpotShow's local-first design does not control SpotPlayer's behavior.

## 🚀 Getting Started

### Requirements

- Python **3.9 or newer**
- SpotPlayer installed if you want to open protected `.spot` content in the official player
- Git (optional, for cloning)

### Install and run

1. Clone the repository:

   ```bash
   git clone https://github.com/ReCode1324/SpotShow.git
   cd SpotShow
   ```

   Alternatively, download the repository as a ZIP file and extract it.

2. (Recommended) Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

   Activate it on **Windows (Command Prompt)**:

   ```cmd
   .venv\Scripts\activate.bat
   ```

3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Launch SpotShow:

   ```bash
   python spotshow.py
   ```

## 📦 Build a Windows Executable

To package SpotShow as a windowed Windows application, install PyInstaller and build the project:

```cmd
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name SpotShow spotshow.py
```

The executable will be generated at:

```text
dist\SpotShow\SpotShow.exe
```

> **Note:** This is a **one-folder** build. Keep the other files in `dist\SpotShow\` alongside the executable when distributing it.

## 🙏 Acknowledgments

Special thanks to **[Mohsen (@MOH12EN)](https://t.me/MOH12EN)** and the **[Deep Package community](https://t.me/Deeppackage)** for their technical insights, support, and contributions to the learning and development process behind this project.

## ⚖️ Disclaimer

SpotShow is an independent, open-source community project. It is **not affiliated with, endorsed by, or sponsored by SpotPlayer**.

It is intended for organizing locally available metadata and accessing content you have legitimately obtained. SpotShow does not decrypt protected content, extract DRM materials, or replace the official SpotPlayer playback engine.
