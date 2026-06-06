#!/usr/bin/env python3
"""
Quick verification script for Calendar Matching app setup
"""

import os
import sys
from pathlib import Path

def check_env():
    """Check if .env file exists and has required variables"""
    print("📋 Checking environment setup...")
    
    env_file = Path(".env")
    if not env_file.exists():
        print("   ❌ .env file not found!")
        print("   💡 Run: cp .env.example .env")
        return False
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET", 
        "ENCRYPTION_KEY"
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.endswith("_here"):
            print(f"   ❌ {var} not configured")
            missing.append(var)
        else:
            print(f"   ✅ {var} configured")
    
    if missing:
        print(f"\n   💡 Edit .env and fill in these values:")
        print(f"      {', '.join(missing)}")
        print(f"   📖 See cloud_configuration.md for instructions")
        return False
    
    return True


def check_dependencies():
    """Check if all dependencies are installed"""
    print("\n📦 Checking dependencies...")
    
    required = [
        "fastapi",
        "uvicorn",
        "httpx",
        "sqlalchemy",
        "cryptography",
        "pydantic",
        "dotenv"
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"\n   💡 Install with: uv sync")
        return False
    
    return True


def check_database():
    """Check if database can be created"""
    print("\n🗄️  Checking database...")
    
    db_file = Path("calendar.db")
    if db_file.exists():
        print(f"   ✅ Database exists ({db_file.stat().st_size} bytes)")
    else:
        print(f"   ℹ️  Database will be created on first run")
    
    return True


def main():
    """Run all checks"""
    print("=" * 50)
    print("Calendar Matching - Setup Verification")
    print("=" * 50)
    
    checks = [
        ("Environment", check_env()),
        ("Dependencies", check_dependencies()),
        ("Database", check_database()),
    ]
    
    print("\n" + "=" * 50)
    print("Summary:")
    print("=" * 50)
    
    all_good = True
    for name, result in checks:
        status = "✅ OK" if result else "❌ FAILED"
        print(f"{name:.<40} {status}")
        if not result:
            all_good = False
    
    print("=" * 50)
    
    if all_good:
        print("\n🚀 All checks passed! You can start the app with:")
        print("   python app.py")
        print("\nThen open in your browser:")
        print("   http://127.0.0.1:8000/docs")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
