"""
main.py — Application entry point.

Keeps bootstrap concerns (sys.path, future env setup) separate from
the App class so neither has to know about the other's concerns.
"""

from src.ui.app import App

if __name__ == "__main__":
    App().run()
