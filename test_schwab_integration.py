"""
Test Suite for Schwab Direct API Integration
Tests OAuth, API connector, data transformation, and integration
"""

import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# Import components to test
from components.schwab_oauth import SchwabOAuth, TokenManager
from components.schwab_connector import SchwabAPI, SchwabConnector
from components.schwab_data_transformer import SchwabDataTransformer


class TestSchwabOAuth:
    """Test OAuth 2.0 authentication with PKCE"""
    
    def test_pkce_generation(self):
        """Test PKCE code verifier and challenge generation"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost")
        
        code_verifier, code_challenge = oauth.generate_pkce_pair()
        
        assert len(code_verifier) > 0
        assert len(code_challenge) > 0
        assert code_verifier != code_challenge
        assert '=' not in code_verifier  # Base64 padding removed
        assert '=' not in code_challenge
    
    def test_authorization_url_generation(self):
        """Test authorization URL generation"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost/callback")
        
        auth_url, code_verifier = oauth.get_authorization_url()
        
        assert "https://api.schwabapi.com/v1/oauth/authorize" in auth_url
        assert "client_id=test_key" in auth_url
        assert "redirect_uri=http" in auth_url
        assert "response_type=code" in auth_url
        assert "scope=api" in auth_url
        assert "code_challenge=" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert len(code_verifier) > 0
    
    def test_callback_url_parsing(self):
        """Test extraction of authorization code from callback URL"""
        callback_url = "http://localhost/callback?code=test_auth_code_123&state=xyz"
        
        auth_code = SchwabOAuth.parse_callback_url(callback_url)
        
        assert auth_code == "test_auth_code_123"
    
    def test_callback_url_parsing_error(self):
        """Test handling of callback URL with error"""
        callback_url = "http://localhost/callback?error=access_denied&error_description=User+denied"
        
        auth_code = SchwabOAuth.parse_callback_url(callback_url)
        
        assert auth_code is None
    
    def test_token_expiration_check(self):
        """Test token expiration detection"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost")
        
        # Expired token
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        assert oauth.is_token_expired(expired_time) is True
        
        # Valid token
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        assert oauth.is_token_expired(future_time) is False
        
        # About to expire (within 5 min buffer)
        soon_time = (datetime.now() + timedelta(minutes=3)).isoformat()
        assert oauth.is_token_expired(soon_time) is True
    
    @patch('components.schwab_oauth.requests.post')
    def test_token_exchange(self, mock_post):
        """Test authorization code exchange for tokens"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost")
        oauth.code_verifier = "test_verifier"
        
        # Mock successful token response
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 1800,
            'token_type': 'Bearer'
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        token_data = oauth.exchange_code_for_token("test_auth_code")
        
        assert token_data['access_token'] == 'test_access_token'
        assert token_data['refresh_token'] == 'test_refresh_token'
        assert 'expires_at' in token_data
        mock_post.assert_called_once()
    
    @patch('components.schwab_oauth.requests.post')
    def test_token_refresh(self, mock_post):
        """Test access token refresh"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost")
        
        # Mock successful refresh response
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'expires_in': 1800,
            'token_type': 'Bearer'
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        token_data = oauth.refresh_access_token("test_refresh_token")
        
        assert token_data['access_token'] == 'new_access_token'
        assert 'expires_at' in token_data
        mock_post.assert_called_once()


class TestTokenManager:
    """Test token lifecycle management"""
    
    def test_token_storage(self):
        """Test storing tokens"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost")
        manager = TokenManager(oauth)
        
        token_data = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        manager.set_tokens(token_data)
        
        assert manager.access_token == 'test_token'
        assert manager.refresh_token == 'test_refresh'
        assert manager.expires_at is not None
    
    def test_get_valid_token_no_refresh_needed(self):
        """Test getting valid token when not expired"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost")
        manager = TokenManager(oauth)
        
        token_data = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        manager.set_tokens(token_data)
        
        token = manager.get_valid_access_token()
        
        assert token == 'test_token'
    
    @patch.object(SchwabOAuth, 'refresh_access_token')
    def test_get_valid_token_with_refresh(self, mock_refresh):
        """Test automatic token refresh when expired"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost")
        manager = TokenManager(oauth)
        
        # Set expired token
        token_data = {
            'access_token': 'old_token',
            'refresh_token': 'test_refresh',
            'expires_at': (datetime.now() - timedelta(hours=1)).isoformat()
        }
        manager.set_tokens(token_data)
        
        # Mock refresh response
        mock_refresh.return_value = {
            'access_token': 'new_token',
            'refresh_token': 'test_refresh',
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        token = manager.get_valid_access_token()
        
        assert token == 'new_token'
        mock_refresh.assert_called_once_with('test_refresh')
    
    def test_clear_tokens(self):
        """Test clearing stored tokens"""
        oauth = SchwabOAuth("test_key", "test_secret", "http://localhost")
        manager = TokenManager(oauth)
        
        token_data = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        manager.set_tokens(token_data)
        
        manager.clear_tokens()
        
        assert manager.access_token is None
        assert manager.refresh_token is None
        assert manager.expires_at is None


class TestSchwabAPI:
    """Test Schwab API client"""
    
    @patch('components.schwab_connector.requests.request')
    def test_get_account_numbers(self, mock_request):
        """Test fetching account numbers"""
        api = SchwabAPI("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {"accountNumber": "12345", "hashValue": "hash1"},
            {"accountNumber": "67890", "hashValue": "hash2"}
        ]
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_request.return_value = mock_response
        
        accounts = api.get_account_numbers()
        
        assert len(accounts) == 2
        assert accounts[0]['accountNumber'] == "12345"
        mock_request.assert_called_once()
    
    @patch('components.schwab_connector.requests.request')
    def test_get_account_details(self, mock_request):
        """Test fetching account details"""
        api = SchwabAPI("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "securitiesAccount": {
                "accountNumber": "12345",
                "type": "MARGIN",
                "positions": [],
                "currentBalances": {
                    "liquidationValue": 100000.00,
                    "cashBalance": 5000.00
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_request.return_value = mock_response
        
        account = api.get_account_details("hash123")
        
        assert account['securitiesAccount']['accountNumber'] == "12345"
        assert account['securitiesAccount']['type'] == "MARGIN"
        mock_request.assert_called_once()
    
    @patch('components.schwab_connector.requests.request')
    def test_get_quotes(self, mock_request):
        """Test fetching real-time quotes"""
        api = SchwabAPI("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "AAPL": {
                "symbol": "AAPL",
                "lastPrice": 150.00,
                "bidPrice": 149.95,
                "askPrice": 150.05
            }
        }
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_request.return_value = mock_response
        
        quotes = api.get_quotes(["AAPL"])
        
        assert "AAPL" in quotes
        assert quotes["AAPL"]["lastPrice"] == 150.00
        mock_request.assert_called_once()


class TestSchwabDataTransformer:
    """Test data transformation utilities"""
    
    def test_transform_positions_to_portfolio(self):
        """Test transforming Schwab positions to portfolio format"""
        transformer = SchwabDataTransformer()
        
        positions_data = [
            {
                'account_number': '12345',
                'position': {
                    'instrument': {
                        'symbol': 'AAPL',
                        'description': 'Apple Inc',
                        'assetType': 'EQUITY'
                    },
                    'longQuantity': 100,
                    'shortQuantity': 0,
                    'averagePrice': 150.00,
                    'marketValue': 15500.00
                }
            }
        ]
        
        portfolio_df = transformer.transform_positions_to_portfolio(positions_data)
        
        assert not portfolio_df.empty
        assert len(portfolio_df) == 1
        assert portfolio_df.iloc[0]['symbol'] == 'AAPL'
        assert portfolio_df.iloc[0]['qty'] == 100
        assert portfolio_df.iloc[0]['purchase_price'] == 150.00
        assert portfolio_df.iloc[0]['sector'] == 'Stock'
    
    def test_transform_empty_positions(self):
        """Test handling empty positions list"""
        transformer = SchwabDataTransformer()
        
        portfolio_df = transformer.transform_positions_to_portfolio([])
        
        assert portfolio_df.empty
    
    def test_transform_transactions(self):
        """Test transforming Schwab transactions"""
        transformer = SchwabDataTransformer()
        
        transactions = [
            {
                'activityId': 123456,
                'type': 'TRADE',
                'tradeDate': '2024-01-15',
                'settlementDate': '2024-01-17',
                'netAmount': -15000.00,
                'transferItems': [
                    {
                        'instrument': {
                            'symbol': 'AAPL',
                            'description': 'Apple Inc'
                        },
                        'amount': 100,
                        'price': 150.00
                    }
                ]
            }
        ]
        
        txn_df = transformer.transform_transactions(transactions, "12345")
        
        assert not txn_df.empty
        assert len(txn_df) == 1
        assert txn_df.iloc[0]['symbol'] == 'AAPL'
        assert txn_df.iloc[0]['quantity'] == 100
        assert txn_df.iloc[0]['price'] == 150.00
    
    def test_transform_quotes(self):
        """Test transforming quote data"""
        transformer = SchwabDataTransformer()
        
        quotes_data = {
            'AAPL': {
                'symbol': 'AAPL',
                'description': 'Apple Inc',
                'lastPrice': 150.00,
                'bidPrice': 149.95,
                'askPrice': 150.05,
                'netChange': 2.50,
                'netPercentChange': 1.69
            }
        }
        
        quotes_df = transformer.transform_quotes(quotes_data)
        
        assert not quotes_df.empty
        assert len(quotes_df) == 1
        assert quotes_df.iloc[0]['symbol'] == 'AAPL'
        assert quotes_df.iloc[0]['last_price'] == 150.00
        assert quotes_df.iloc[0]['change'] == 2.50
    
    def test_merge_with_existing_portfolio(self):
        """Test merging Schwab positions with existing portfolio"""
        transformer = SchwabDataTransformer()
        
        schwab_positions = pd.DataFrame([
            {
                'symbol': 'AAPL',
                'qty': 100,
                'purchase_price': 150.00,
                'account_name': 'Schwab-1234'
            }
        ])
        
        existing_portfolio = pd.DataFrame([
            {
                'symbol': 'MSFT',
                'qty': 50,
                'purchase_price': 300.00,
                'account_name': 'Manual-Entry'
            }
        ])
        
        merged_df = transformer.merge_with_existing_portfolio(
            schwab_positions,
            existing_portfolio
        )
        
        assert len(merged_df) == 2
        assert 'source' in merged_df.columns
        assert merged_df[merged_df['symbol'] == 'AAPL'].iloc[0]['source'] == 'Schwab'
        assert merged_df[merged_df['symbol'] == 'MSFT'].iloc[0]['source'] == 'Manual'


class TestSchwabConnector:
    """Test high-level Schwab connector"""
    
    @patch('components.schwab_connector.CredentialManager')
    def test_connector_initialization(self, mock_cred_manager):
        """Test connector initialization"""
        connector = SchwabConnector(
            "test_key",
            "test_secret",
            "http://localhost"
        )
        
        assert connector.oauth is not None
        assert connector.token_manager is not None
        assert connector.api is None  # Not connected yet
    
    @patch('components.schwab_connector.CredentialManager')
    def test_get_authorization_url(self, mock_cred_manager):
        """Test getting authorization URL"""
        connector = SchwabConnector(
            "test_key",
            "test_secret",
            "http://localhost"
        )
        
        auth_url = connector.get_authorization_url()
        
        assert "https://api.schwabapi.com" in auth_url
        assert hasattr(connector, '_code_verifier')
    
    @patch('components.schwab_connector.CredentialManager')
    @patch.object(SchwabOAuth, 'parse_callback_url')
    @patch.object(SchwabOAuth, 'exchange_code_for_token')
    def test_complete_authorization(self, mock_exchange, mock_parse, mock_cred_manager):
        """Test completing OAuth authorization"""
        connector = SchwabConnector(
            "test_key",
            "test_secret",
            "http://localhost"
        )
        connector._code_verifier = "test_verifier"
        
        # Mock callback parsing
        mock_parse.return_value = "test_auth_code"
        
        # Mock token exchange
        mock_exchange.return_value = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        success = connector.complete_authorization("http://localhost?code=test_auth_code")
        
        assert success is True
        assert connector.api is not None
        mock_parse.assert_called_once()
        mock_exchange.assert_called_once()


class TestIntegration:
    """Integration tests for end-to-end flows"""
    
    @patch('components.schwab_connector.CredentialManager')
    @patch('components.schwab_connector.requests.request')
    def test_full_sync_flow(self, mock_request, mock_cred_manager):
        """Test complete sync flow from auth to data transformation"""
        # This would be a more complex integration test
        # that tests the full flow of authentication -> API calls -> data transformation
        pass


# Test fixtures
@pytest.fixture
def sample_schwab_positions():
    """Sample Schwab position data"""
    return [
        {
            'account_number': '12345',
            'position': {
                'instrument': {
                    'symbol': 'AAPL',
                    'description': 'Apple Inc',
                    'assetType': 'EQUITY'
                },
                'longQuantity': 100,
                'averagePrice': 150.00,
                'marketValue': 15500.00
            }
        },
        {
            'account_number': '12345',
            'position': {
                'instrument': {
                    'symbol': 'MSFT',
                    'description': 'Microsoft Corp',
                    'assetType': 'EQUITY'
                },
                'longQuantity': 50,
                'averagePrice': 300.00,
                'marketValue': 15250.00
            }
        }
    ]


@pytest.fixture
def sample_schwab_transactions():
    """Sample Schwab transaction data"""
    return [
        {
            'activityId': 123456,
            'type': 'TRADE',
            'tradeDate': '2024-01-15',
            'netAmount': -15000.00,
            'transferItems': [
                {
                    'instrument': {'symbol': 'AAPL'},
                    'amount': 100,
                    'price': 150.00
                }
            ]
        }
    ]


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])

# Made with Bob
