"""Database helper commands.

  python manage.py init-db   create the tables (safe to run again)
  python manage.py seed      add demo data when the database is empty
  python manage.py reset     wipe everything and add demo data again
"""
import sys

from studysync.config import load_config
from studysync.db import init_db
from studysync.seed import DEMO_PASSWORD, seed_database


def main(argv):
    command = argv[1] if len(argv) > 1 else ""
    path = load_config()["DATABASE"]
    if command == "init-db":
        init_db(path)
        print(f"Created tables in {path}")
    elif command in ("seed", "reset"):
        added = seed_database(path, reset=(command == "reset"))
        print(f"Demo data added to {path}. Log in with demo@studysync.app / {DEMO_PASSWORD}" if added else f"{path} already has users; run 'python manage.py reset' to start over.")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
