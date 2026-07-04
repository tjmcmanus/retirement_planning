"""
test_snaptrade_setup.py
=======================
Test script to verify SnapTrade integration setup.

Run this after configuring .env file to ensure everything is working.
"""

import os
import sys


def test_environment_variables():
    """Test that required environment variables are set."""
    print("=" * 60)
    print("Testing Environment Variables")
    print("=" * 60)
    
    required_vars = [
        'SNAPTRADE_CLIENT_ID',
        'SNAPTRADE_CONSUMER_KEY',
        'ENCRYPTION_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Show first/last 4 chars only for security
            masked = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
            print(f"✅ {var}: {masked}")
        else:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Missing variables: {', '.join(missing_vars)}")
        print("\nPlease set these in your .env file:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your actual credentials")
        return False
    
    print("\n✅ All environment variables are set")
    return True


def test_dependencies():
    """Test that required packages are installed."""
    print("\n" + "=" * 60)
    print("Testing Dependencies")
    print("=" * 60)
    
    required_packages = [
        ('cryptography.fernet', 'Fernet'),
        ('snaptrade_client', 'SnapTrade'),
        ('dotenv', 'load_dotenv'),
        ('pandas', 'DataFrame'),
        ('streamlit', 'write')
    ]
    
    missing_packages = []
    for package, attr in required_packages:
        try:
            module = __import__(package)
            if hasattr(module, attr):
                print(f"✅ {package}: installed")
            else:
                print(f"⚠️  {package}: installed but missing {attr}")
        except ImportError:
            print(f"❌ {package}: NOT INSTALLED")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("\nInstall with: pip install -r requirements.txt")
        return False
    
    print("\n✅ All dependencies are installed")
    return True


def test_credential_manager():
    """Test credential manager initialization."""
    print("\n" + "=" * 60)
    print("Testing Credential Manager")
    print("=" * 60)
    
    try:
        from components.credential_manager import CredentialManager
        
        # Test initialization
        cred_manager = CredentialManager()
        print("✅ Credential manager initialized")
        
        # Test encryption/decryption
        test_data = "test_secret_123"
        encrypted = cred_manager.encrypt(test_data)
        decrypted = cred_manager.decrypt(encrypted)
        
        if decrypted == test_data:
            print("✅ Encryption/decryption working")
        else:
            print("❌ Encryption/decryption failed")
            return False
        
        # Test database
        connections = cred_manager.list_connections()
        print(f"✅ Database accessible ({len(connections)} connections)")
        
        return True
        
    except Exception as e:
        print(f"❌ Credential manager failed: {e}")
        return False


def test_snaptrade_connector():
    """Test SnapTrade connector initialization."""
    print("\n" + "=" * 60)
    print("Testing SnapTrade Connector")
    print("=" * 60)
    
    try:
        from components.snaptrade_connector import create_snaptrade_connector, SNAPTRADE_AVAILABLE
        
        if not SNAPTRADE_AVAILABLE:
            print("❌ SnapTrade library not available")
            print("Install with: pip install snaptrade-python")
            return False
        
        # Test initialization
        connector = create_snaptrade_connector()
        print("✅ SnapTrade connector initialized")
        
        # Test connection status (doesn't require auth)
        try:
            status = connector.get_connection_status()
            print(f"✅ Connection status retrieved")
            print(f"   Connected: {status.get('connected', False)}")
            print(f"   Accounts: {status.get('account_count', 0)}")
        except Exception as e:
            print(f"⚠️  Connection status check failed: {e}")
            print("   This is normal if you haven't connected any accounts yet")
        
        return True
        
    except Exception as e:
        print(f"❌ SnapTrade connector failed: {e}")
        print("\nPossible issues:")
        print("1. Check SNAPTRADE_CLIENT_ID and SNAPTRADE_CONSUMER_KEY in .env")
        print("2. Verify credentials are correct in SnapTrade dashboard")
        print("3. Check if you're using the right environment (sandbox vs production)")
        return False


def test_ui_component():
    """Test UI component can be imported."""
    print("\n" + "=" * 60)
    print("Testing UI Component")
    print("=" * 60)
    
    try:
        from components.portfolio_connections import render_connections_tab
        print("✅ UI component can be imported")
        return True
    except Exception as e:
        print(f"❌ UI component import failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SnapTrade Integration Setup Test")
    print("=" * 60)
    print()
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded .env file\n")
    except ImportError:
        print("⚠️  python-dotenv not installed, using system environment variables\n")
    except Exception as e:
        print(f"⚠️  Could not load .env file: {e}\n")
    
    # Run tests
    results = {
        'Environment Variables': test_environment_variables(),
        'Dependencies': test_dependencies(),
        'Credential Manager': test_credential_manager(),
        'SnapTrade Connector': test_snaptrade_connector(),
        'UI Component': test_ui_component()
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Setup complete! You're ready to connect brokerage accounts.")
        print("\nNext steps:")
        print("1. Start the app: streamlit run planning_app.py")
        print("2. Navigate to Portfolio Hub → Connections tab")
        print("3. Click 'Connect Account' to link your brokerage")
        return 0
    else:
        print("\n❌ Setup incomplete. Please fix the issues above.")
        print("\nFor help, see:")
        print("- SNAPTRADE_QUICKSTART.md")
        print("- SNAPTRADE_INTEGRATION_PLAN.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
