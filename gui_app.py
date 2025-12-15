#!/usr/bin/env python3
"""GUI application entry point for Open-AutoGLM."""

import sys

from PyQt5.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    """Main entry point for the GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Open-AutoGLM GUI")
    app.setOrganizationName("Open-AutoGLM GUI")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

