# Third-party components

Computer Connect's own source is MIT; it is implemented separately from `app/`.

- Python 3.12 / Tkinter and Tcl/Tk: PSF and Tcl/Tk notices; https://www.python.org/ and https://www.tcl.tk/software/tcltk/license.html
- websocket-client 1.9.2: Apache-2.0; https://github.com/websocket-client/websocket-client
- Pillow 13.0.0 and its bundled image libraries: MIT-CMU and the upstream bundled-library notices; https://github.com/python-pillow/Pillow
- PyInstaller 6.22.3 (build/bootloader): GPL-2.0-or-later with the PyInstaller bootloader exception; https://pyinstaller.org/en/stable/license.html

The executable must be distributed with the collected third-party license files
and its corresponding source/reproducible build instructions. Do not remove
upstream notices or represent these dependencies as authored by Couchside.
No ViGEm DLL/driver, mobile-app code, credentials, certificates or game files are
bundled in the client. No SignPath certificate or signing approval is included.

- Space Mono font: SIL Open Font License 1.1; included assets/SpaceMono-OFL.txt. Couchside brand images are from the MIT brand/ directory. No mobile-app component source is imported.
