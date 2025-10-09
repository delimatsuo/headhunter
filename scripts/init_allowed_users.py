#!/usr/bin/env python3
"""
Initialize the allowed_users collection in Firestore with initial admin users.

This script seeds the allowed_users collection with one or more admin users
to bootstrap the authentication and authorization system. It's safe to run
multiple times (idempotent) and works with both the Firestore emulator and
production Firestore.

Usage:
    # Using environment variables
    export ADMIN_EMAILS="admin@ella.com.br,manager@ella.com.br"
    python3 scripts/init_allowed_users.py

    # Using command-line arguments
    python3 scripts/init_allowed_users.py admin@ella.com.br manager@ella.com.br

    # Specify role (default is 'admin')
    python3 scripts/init_allowed_users.py --role=super_admin admin@ella.com.br

Environment Variables:
    ADMIN_EMAILS: Comma-separated list of admin email addresses
    GOOGLE_APPLICATION_CREDENTIALS: Path to service account key (for production)
    FIRESTORE_EMULATOR_HOST: Firestore emulator host (for local development)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import List

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("Error: firebase-admin package not installed")
    print("Install with: pip install firebase-admin")
    sys.exit(1)


class AllowedUsersInitializer:
    """Initialize the allowed_users collection with admin users."""

    VALID_ROLES = ['admin', 'recruiter', 'super_admin']
    DEFAULT_ROLE = 'admin'

    def __init__(self):
        """Initialize Firebase connection."""
        self.is_emulator = 'FIRESTORE_EMULATOR_HOST' in os.environ

        if self.is_emulator:
            # Use emulator (no credentials needed)
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            print(f"✓ Connected to Firestore emulator: {os.environ['FIRESTORE_EMULATOR_HOST']}")
        else:
            # Use production (requires credentials)
            cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            if not cred_path:
                print("Error: GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
                print("Set it to the path of your service account key file")
                sys.exit(1)

            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            print(f"✓ Connected to production Firestore")

        self.db = firestore.client()

    @staticmethod
    def normalize_email(email: str) -> str:
        """Normalize email to lowercase."""
        return email.strip().lower()

    @staticmethod
    def email_to_doc_id(email: str) -> str:
        """Convert email to Firestore document ID."""
        return AllowedUsersInitializer.normalize_email(email).replace('/', '_')

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        return bool(re.match(pattern, email))

    def add_allowed_user(self, email: str, role: str = DEFAULT_ROLE, created_by: str = 'system') -> bool:
        """
        Add a user to the allowed_users collection.

        Args:
            email: User's email address
            role: User's role (admin, recruiter, or super_admin)
            created_by: UID of the admin who created this user (defaults to 'system')

        Returns:
            True if user was created, False if user already exists
        """
        if not self.validate_email(email):
            print(f"✗ Invalid email format: {email}")
            return False

        if role not in self.VALID_ROLES:
            print(f"✗ Invalid role: {role}. Must be one of {self.VALID_ROLES}")
            return False

        normalized_email = self.normalize_email(email)
        doc_id = self.email_to_doc_id(normalized_email)

        # Check if user already exists
        doc_ref = self.db.collection('allowed_users').document(doc_id)
        doc = doc_ref.get()

        now = firestore.SERVER_TIMESTAMP

        if doc.exists:
            # Update existing user
            doc_ref.update({
                'role': role,
                'updated_at': now
            })
            print(f"✓ Updated existing user: {normalized_email} (role: {role})")
            return False
        else:
            # Create new user
            doc_ref.set({
                'email': normalized_email,
                'role': role,
                'created_at': now,
                'created_by': created_by,
                'updated_at': now
            })
            print(f"✓ Created new user: {normalized_email} (role: {role})")
            return True

    def list_allowed_users(self) -> List[dict]:
        """List all users in the allowed_users collection."""
        docs = self.db.collection('allowed_users').order_by('email').stream()
        users = []
        for doc in docs:
            data = doc.to_dict()
            users.append({
                'id': doc.id,
                'email': data.get('email'),
                'role': data.get('role'),
                'created_at': data.get('created_at'),
                'created_by': data.get('created_by')
            })
        return users


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Initialize allowed_users collection with admin users',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'emails',
        nargs='*',
        help='Email addresses to add as admin users'
    )
    parser.add_argument(
        '--role',
        default=AllowedUsersInitializer.DEFAULT_ROLE,
        choices=AllowedUsersInitializer.VALID_ROLES,
        help=f'Role to assign to users (default: {AllowedUsersInitializer.DEFAULT_ROLE})'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all users in allowed_users collection'
    )
    parser.add_argument(
        '--created-by',
        default='system',
        help='UID of the admin creating these users (default: system)'
    )

    args = parser.parse_args()

    # Initialize Firestore connection
    try:
        initializer = AllowedUsersInitializer()
    except Exception as e:
        print(f"✗ Failed to initialize Firestore connection: {e}")
        return 1

    # List users if requested
    if args.list:
        print("\n📋 Allowed Users:")
        print("-" * 80)
        users = initializer.list_allowed_users()
        if not users:
            print("(no users found)")
        else:
            for user in users:
                created_at = user['created_at'].strftime('%Y-%m-%d %H:%M:%S') if user['created_at'] else 'N/A'
                print(f"  {user['email']:<40} {user['role']:<15} created by: {user['created_by']}")
        print()
        return 0

    # Get emails from command-line args or environment variable
    emails = args.emails if args.emails else []
    if not emails:
        env_emails = os.environ.get('ADMIN_EMAILS', '')
        if env_emails:
            emails = [e.strip() for e in env_emails.split(',') if e.strip()]

    if not emails:
        print("Error: No email addresses provided")
        print("Provide emails via command-line arguments or ADMIN_EMAILS environment variable")
        print()
        parser.print_help()
        return 1

    # Add users
    print(f"\n🔐 Initializing allowed_users collection")
    print(f"   Role: {args.role}")
    print(f"   Created by: {args.created_by}")
    print("-" * 80)

    created_count = 0
    updated_count = 0

    for email in emails:
        if initializer.add_allowed_user(email, role=args.role, created_by=args.created_by):
            created_count += 1
        else:
            updated_count += 1

    print("-" * 80)
    print(f"✓ Complete: {created_count} users created, {updated_count} users updated")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
