#!/usr/bin/env python3
"""
Command-line tool to generate JWT access tokens.
"""

import secrets

import click


def create_access_token():
    return secrets.token_urlsafe(64)


@click.command()
def main():
    """Generate access token.

    python generate_token.py
    """

    # Generate token
    token = create_access_token()

    # Display results
    click.echo()
    click.echo("=" * 80)
    click.echo(click.style(f"Access Token:\n{token}", fg="green", bold=True))
    click.echo("=" * 80)
    click.echo()


if __name__ == "__main__":
    main()
