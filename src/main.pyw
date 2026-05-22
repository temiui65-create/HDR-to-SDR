import os
import sys

# [핵심] macOS에서 앱 번들로 실행 시, tkinterdnd2가 내장 tkdnd 라이브러리를 
# 찾지 못해 시작하자마자 강제 종료되는 문제를 방지합니다.
if getattr(sys, 'frozen', False) and sys.platform == 'darwin':
    meipass = sys._MEIPASS
    # 패키징된 라이브러리 경로를 환경 변수에 강제로 주입
    tkdnd_paths = [
        os.path.join(meipass, 'tkinterdnd2', 'tkdnd'),
        os.path.join(meipass, 'tkinterdnd2')
    ]
    for path in tkdnd_paths:
        if os.path.exists(path):
            os.environ['TKDND_LIBRARY'] = path
            break

# 반드시 위의 경로 설정 코드가 실행된 "이후"에 tkinterdnd2를 임포트해야 합니다.
import tkinter as tk
from tkinterdnd2 import TkinterDnD, DND_FILES
from gui import HDRConverterGUI
from PIL import Image

"""
This script initializes and runs a Tkinter GUI application.
Modules:
    tkinter: Standard Python interface to the Tk GUI toolkit.
    gui: Custom module containing the class to create the main window.
Functions:
    create_main_window(root): Sets up the main window of the application.
Execution:
    When run as the main module, this script creates the main TkinterDnD window,
    sets up the main window using the HDRConverterGUI class, and starts
    the Tkinter main event loop.
"""

if __name__ == "__main__":
    # Create the main TkinterDnD window
    root = TkinterDnD.Tk()
    app = HDRConverterGUI(root)
    root.mainloop()
