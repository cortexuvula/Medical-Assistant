#!/usr/bin/env python3
"""
Command-line utility for managing API keys securely.
"""

import sys
import os
import getpass
import argparse
from datetime import datetime
from pathlib import Path

from src.utils.security import get_security_manager
from src.core.config import get_config


def add_key(args):
    """Add or update an API key."""
    provider = args.provider.lower()
    
    # Get API key
    if args.key:
        api_key = args.key
    else:
        # Prompt for key (hidden input)
        api_key = getpass.getpass(f"Enter {provider.upper()} API key: ")
    
    if not api_key:
        print("Error: API key cannot be empty")
        return 1
    
    # Store the key
    security_manager = get_security_manager()
    success, error = security_manager.store_api_key(provider, api_key)
    
    if success:
        print(f"✓ Successfully stored API key for {provider}")
        return 0
    else:
        print(f"✗ Failed to store API key: {error}")
        return 1


def remove_key(args):
    """Remove a stored API key."""
    provider = args.provider.lower()
    
    # Confirm removal
    if not args.force:
        confirm = input(f"Remove API key for {provider}? (y/N): ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return 0
    
    # Remove the key
    security_manager = get_security_manager()
    if security_manager.key_storage.remove_key(provider):
        print(f"✓ Removed API key for {provider}")
        return 0
    else:
        print(f"✗ No API key found for {provider}")
        return 1


def list_keys(args):
    """List stored API keys (without showing the actual keys)."""
    security_manager = get_security_manager()
    providers = security_manager.key_storage.list_providers()
    
    if not providers:
        print("No API keys stored")
        return 0
    
    print("Stored API Keys:")
    print("-" * 50)
    
    for provider, metadata in providers.items():
        stored_at = metadata.get("stored_at", "Unknown")
        key_hash = metadata.get("key_hash", "Unknown")
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(stored_at)
            stored_at = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        
        print(f"{provider:15} Stored: {stored_at}  Hash: {key_hash}")
    
    return 0


def validate_key(args):
    """Validate an API key."""
    provider = args.provider.lower()
    
    # Get API key
    security_manager = get_security_manager()
    api_key = security_manager.get_api_key(provider)
    
    if not api_key:
        print(f"✗ No API key found for {provider}")
        print(f"  Check environment variable {provider.upper()}_API_KEY or add with 'manage_keys add'")
        return 1
    
    # Validate the key
    is_valid, error = security_manager.validate_api_key(provider, api_key)
    
    if is_valid:
        print(f"✓ {provider} API key is valid")
        return 0
    else:
        print(f"✗ {provider} API key validation failed: {error}")
        return 1


def check_all(args):
    """Check all API keys."""
    providers = ["openai", "perplexity", "groq", "deepgram", "elevenlabs"]
    security_manager = get_security_manager()
    config = get_config()
    
    print("API Key Status:")
    print("-" * 60)
    
    all_valid = True
    
    for provider in providers:
        # Check if key exists
        api_key = security_manager.get_api_key(provider)
        
        if api_key:
            # Validate the key
            is_valid, error = security_manager.validate_api_key(provider, api_key)
            
            if is_valid:
                # Check source
                env_key = config.get_api_key(provider)
                source = "environment" if env_key else "secure storage"
                print(f"✓ {provider:12} Valid ({source})")
            else:
                print(f"✗ {provider:12} Invalid: {error}")
                all_valid = False
        else:
            print(f"✗ {provider:12} Not configured")
            all_valid = False
    
    print("-" * 60)
    
    if all_valid:
        print("✓ All API keys are valid")
        return 0
    else:
        print("✗ Some API keys are missing or invalid")
        print("\nTo add a key: python manage_keys.py add <provider>")
        return 1


def export_env(args):
    """Export API keys as environment variables."""
    security_manager = get_security_manager()
    providers = security_manager.key_storage.list_providers()
    
    if not providers:
        print("# No API keys stored")
        return 0
    
    print("# Medical Assistant API Keys")
    print(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("# Add these to your .env file or shell profile")
    print()
    
    for provider in providers:
        api_key = security_manager.get_api_key(provider)
        if api_key:
            env_var = f"{provider.upper()}_API_KEY"
            if args.shell == "bash":
                print(f"export {env_var}=\"{api_key}\"")
            elif args.shell == "fish":
                print(f"set -x {env_var} \"{api_key}\"")
            elif args.shell == "powershell":
                print(f"$env:{env_var} = \"{api_key}\"")
            else:  # .env format
                print(f"{env_var}={api_key}")
    
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage API keys for Medical Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  manage_keys.py add openai                  # Add OpenAI API key (prompts for key)
  manage_keys.py add groq --key gsk_123...   # Add Groq API key directly
  manage_keys.py remove deepgram             # Remove Deepgram API key
  manage_keys.py list                        # List all stored keys
  manage_keys.py validate openai             # Validate OpenAI key
  manage_keys.py check                       # Check all API keys
  manage_keys.py export                      # Export as .env format
  manage_keys.py export --shell bash         # Export as bash commands
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add or update an API key")
    add_parser.add_argument("provider", help="API provider (openai, groq, etc.)")
    add_parser.add_argument("--key", help="API key (will prompt if not provided)")
    add_parser.set_defaults(func=add_key)
    
    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove an API key")
    remove_parser.add_argument("provider", help="API provider")
    remove_parser.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    remove_parser.set_defaults(func=remove_key)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List stored API keys")
    list_parser.set_defaults(func=list_keys)
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate an API key")
    validate_parser.add_argument("provider", help="API provider")
    validate_parser.set_defaults(func=validate_key)
    
    # Check all command
    check_parser = subparsers.add_parser("check", help="Check all API keys")
    check_parser.set_defaults(func=check_all)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export API keys")
    export_parser.add_argument(
        "--shell", 
        choices=["env", "bash", "fish", "powershell"],
        default="env",
        help="Output format (default: env)"
    )
    export_parser.set_defaults(func=export_env)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Run the command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())