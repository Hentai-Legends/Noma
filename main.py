import sys
import os

# Tambahkan direktori root ke sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.app import run_cli

if __name__ == "__main__":
    run_cli()
