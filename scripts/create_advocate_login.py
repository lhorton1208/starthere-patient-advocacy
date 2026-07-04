"""
Create or update an advocate login from the command line.

Examples:
  python scripts/create_advocate_login.py --advocate "Larry Horton" --username larry --password 'YourPass123' --admin
  python scripts/create_advocate_login.py --advocate-id 1 --username dawn --password 'YourPass123'
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import Advocate, db


def _find_advocate(*, advocate_id=None, advocate_name=None):
    if advocate_id is not None:
        return Advocate.query.get(advocate_id)
    if advocate_name:
        return Advocate.query.filter_by(name=advocate_name).first()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update an advocate login.")
    parser.add_argument("--advocate-id", type=int, help="Advocate database ID")
    parser.add_argument("--advocate", help="Exact advocate name")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--password", help="Login password (prompted if omitted)")
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Grant administrator access for managing logins",
    )
    args = parser.parse_args()

    if not args.advocate_id and not args.advocate:
        parser.error("Provide --advocate-id or --advocate")

    password = args.password
    if password:
        confirm = password
    else:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    username = args.username.strip().lower()
    if len(username) < 3:
        print("Username must be at least 3 characters.", file=sys.stderr)
        return 1

    app = create_app(run_migrate=False)
    with app.app_context():
        advocate = _find_advocate(
            advocate_id=args.advocate_id,
            advocate_name=args.advocate,
        )
        if advocate is None:
            print("Advocate not found.", file=sys.stderr)
            return 1

        existing = Advocate.query.filter(
            Advocate.username == username,
            Advocate.id != advocate.id,
        ).first()
        if existing:
            print(f"Username '{username}' is already in use.", file=sys.stderr)
            return 1

        advocate.username = username
        advocate.set_password(password)
        advocate.is_admin = bool(args.admin)
        db.session.commit()
        print(
            f"Login saved for {advocate.name} "
            f"(username: {username}, admin: {advocate.is_admin})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
