"""Entry point for running as python -m liftosaur_garmin"""
import sys

from .cli import main

if __name__ == '__main__':
    sys.exit(main())