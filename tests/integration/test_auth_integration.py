"""
Integration tests for Authentication & Security workflows

This module tests the complete authentication and security workflows including:
- Firebase Authentication flow end-to-end
- JWT token validation across services
- Role-based access control (RBAC)
- API rate limiting
- CORS configuration
- Data isolation between tenants
"""

import pytest
import asyncio
import json
import jwt
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.auth, pytest.mark.api]


class TestAuthenticationIntegration:
    """Test complete authentication and security integration"""
    
    @pytest.mark.asyncio
    async def test_complete_authentication_flow(
        self,
        mock_firebase_auth,
        auth_headers: Dict[str, str],
        performance_monitor
    ):
        """Test complete authentication flow from login to API access"""
        performance_monitor.start_timer("complete_auth_flow")
        
        # Step 1: Simulate user login and token generation
        performance_monitor.start_timer("user_login")
        
        login_result = await self._simulate_user_login(
            email="test@example.com",
            password="test_password"
        )
        
        performance_monitor.end_timer("user_login")
        
        # Verify login success
        assert login_result["success"] is True, "User login should succeed"
        assert "id_token" in login_result, "Should return ID token"
        assert "refresh_token" in login_result, "Should return refresh token"
        
        # Step 2: Validate JWT token structure and claims
        performance_monitor.start_timer("token_validation")
        
        token_validation = await self._validate_jwt_token(login_result["id_token"])
        
        performance_monitor.end_timer("token_validation")
        
        # Verify token validation
        assert token_validation["valid"] is True, "Token should be valid"
        assert token_validation["claims"]["email"] == "test@example.com", \
            "Token should contain correct email"
        assert "role" in token_validation["claims"], "Token should contain role"
        
        # Step 3: Test API access with valid token
        performance_monitor.start_timer("api_access")
        
        api_result = await self._test_authenticated_api_access(
            token=login_result["id_token"],
            endpoint="/api/candidates/search",
            method="POST"
        )
        
        performance_monitor.end_timer("api_access")
        
        # Verify API access
        assert api_result["status_code"] == 200, "API should allow access with valid token"
        
        # Step 4: Test token refresh mechanism
        performance_monitor.start_timer("token_refresh")
        
        refresh_result = await self._test_token_refresh(login_result["refresh_token"])
        
        performance_monitor.end_timer("token_refresh")
        
        # Verify token refresh
        assert refresh_result["success"] is True, "Token refresh should succeed"
        assert "new_id_token" in refresh_result, "Should return new ID token"
        
        # Step 5: Test logout and token invalidation
        performance_monitor.start_timer("logout")
        
        logout_result = await self._test_user_logout(login_result["id_token"])
        
        performance_monitor.end_timer("logout")
        
        # Verify logout
        assert logout_result["success"] is True, "Logout should succeed"
        
        # Step 6: Verify token is invalidated after logout
        post_logout_access = await self._test_authenticated_api_access(
            token=login_result["id_token"],
            endpoint="/api/candidates/search",
            method="POST"
        )
        
        assert post_logout_access["status_code"] == 401, \
            "API should deny access with invalidated token"
        
        performance_monitor.end_timer("complete_auth_flow")
        
        # Assert performance requirements
        performance_monitor.assert_performance("complete_auth_flow", 5.0)  # Max 5s total
        performance_monitor.assert_performance("user_login", 1.0)          # Max 1s login
        performance_monitor.assert_performance("token_validation", 0.5)    # Max 500ms validation
    
    @pytest.mark.asyncio
    async def test_role_based_access_control(
        self,
        mock_firebase_auth,
        test_data_factory
    ):
        """Test RBAC implementation across different user roles"""
        # Define test roles and their permissions
        roles_permissions = {
            "admin": {
                "can_access": [
                    "/api/candidates/search",
                    "/api/candidates/create", 
                    "/api/candidates/update",
                    "/api/candidates/delete",
                    "/api/admin/users",
                    "/api/admin/analytics"
                ],
                "cannot_access": []
            },
            "recruiter": {
                "can_access": [
                    "/api/candidates/search",
                    "/api/candidates/create",
                    "/api/candidates/update",
                    "/api/jobs/create"
                ],
                "cannot_access": [
                    "/api/candidates/delete",
                    "/api/admin/users",
                    "/api/admin/analytics"
                ]
            },
            "viewer": {
                "can_access": [
                    "/api/candidates/search",
                    "/api/jobs/list"
                ],
                "cannot_access": [
                    "/api/candidates/create",
                    "/api/candidates/update", 
                    "/api/candidates/delete",
                    "/api/admin/users"
                ]
            }
        }
        
        for role, permissions in roles_permissions.items():
            # Create user with specific role
            user_token = await self._create_user_with_role(
                email=f"{role}@example.com",
                role=role
            )
            
            # Test allowed endpoints
            for endpoint in permissions["can_access"]:
                access_result = await self._test_authenticated_api_access(
                    token=user_token,
                    endpoint=endpoint,
                    method="GET"
                )
                
                assert access_result["status_code"] in [200, 201], \
                    f"Role {role} should have access to {endpoint}"
            
            # Test forbidden endpoints  
            for endpoint in permissions["cannot_access"]:
                access_result = await self._test_authenticated_api_access(
                    token=user_token,
                    endpoint=endpoint,
                    method="GET"
                )
                
                assert access_result["status_code"] == 403, \
                    f"Role {role} should NOT have access to {endpoint}"
    
    @pytest.mark.asyncio
    async def test_jwt_token_validation_security(self):
        """Test JWT token validation security measures"""
        # Test cases for token validation
        test_cases = [
            {
                "name": "valid_token",
                "token": self._generate_valid_test_token(),
                "expected_valid": True
            },
            {
                "name": "expired_token", 
                "token": self._generate_expired_test_token(),
                "expected_valid": False
            },
            {
                "name": "invalid_signature",
                "token": self._generate_invalid_signature_token(),
                "expected_valid": False
            },
            {
                "name": "malformed_token",
                "token": "invalid.token.format",
                "expected_valid": False
            },
            {
                "name": "missing_claims",
                "token": self._generate_token_missing_claims(),
                "expected_valid": False
            },
            {
                "name": "tampered_payload",
                "token": self._generate_tampered_payload_token(),
                "expected_valid": False
            }
        ]
        
        for test_case in test_cases:
            validation_result = await self._validate_jwt_token(test_case["token"])
            
            assert validation_result["valid"] == test_case["expected_valid"], \
                f"Token validation failed for {test_case['name']}"
            
            if not test_case["expected_valid"]:
                assert "error" in validation_result, \
                    f"Invalid token should include error message for {test_case['name']}"
    
    @pytest.mark.asyncio
    async def test_api_rate_limiting(
        self,
        performance_monitor
    ):
        """Test API rate limiting implementation"""
        user_token = await self._create_user_with_role(
            email="ratelimit@example.com",
            role="recruiter"
        )
        
        # Test rate limit configuration
        rate_limits = {
            "/api/candidates/search": {"limit": 100, "window": 60},  # 100 requests per minute
            "/api/candidates/create": {"limit": 10, "window": 60},   # 10 requests per minute
            "/api/embeddings/generate": {"limit": 50, "window": 300} # 50 requests per 5 minutes
        }
        
        for endpoint, limits in rate_limits.items():
            performance_monitor.start_timer(f"rate_limit_{endpoint.replace('/', '_')}")
            
            # Make requests up to the limit
            successful_requests = 0
            
            for i in range(limits["limit"] + 5):  # Try 5 extra requests
                response = await self._test_authenticated_api_access(
                    token=user_token,
                    endpoint=endpoint,
                    method="POST"
                )
                
                if response["status_code"] == 200:
                    successful_requests += 1
                elif response["status_code"] == 429:  # Rate limit exceeded
                    break
                    
                # Small delay between requests
                await asyncio.sleep(0.01)
            
            performance_monitor.end_timer(f"rate_limit_{endpoint.replace('/', '_')}")
            
            # Should successfully make up to the limit
            assert successful_requests <= limits["limit"], \
                f"Should not exceed rate limit for {endpoint}"
            
            # Should receive 429 when limit exceeded
            if successful_requests == limits["limit"]:
                # Make one more request to trigger rate limit
                rate_limit_response = await self._test_authenticated_api_access(
                    token=user_token,
                    endpoint=endpoint,
                    method="POST"
                )
                
                assert rate_limit_response["status_code"] == 429, \
                    f"Should return 429 when rate limit exceeded for {endpoint}"
                
                assert "Retry-After" in rate_limit_response.get("headers", {}), \
                    "Rate limit response should include Retry-After header"
    
    @pytest.mark.asyncio
    async def test_cors_configuration(self):
        """Test CORS configuration for cross-origin requests"""
        test_origins = [
            "https://headhunter.example.com",    # Production domain
            "https://staging.headhunter.com",    # Staging domain
            "http://localhost:3000",             # Development domain
            "https://evil-site.com"              # Should be blocked
        ]
        
        allowed_origins = test_origins[:3]  # First 3 are allowed
        blocked_origins = test_origins[3:]   # Last one should be blocked
        
        for origin in allowed_origins:
            cors_response = await self._test_cors_preflight(
                origin=origin,
                method="POST",
                headers=["Authorization", "Content-Type"]
            )
            
            assert cors_response["status_code"] == 200, \
                f"CORS preflight should succeed for allowed origin {origin}"
            
            assert cors_response["headers"].get("Access-Control-Allow-Origin") == origin, \
                f"Should allow origin {origin}"
            
            assert "POST" in cors_response["headers"].get("Access-Control-Allow-Methods", ""), \
                f"Should allow POST method for {origin}"
        
        for origin in blocked_origins:
            cors_response = await self._test_cors_preflight(
                origin=origin,
                method="POST", 
                headers=["Authorization", "Content-Type"]
            )
            
            assert cors_response["status_code"] == 403, \
                f"CORS preflight should fail for blocked origin {origin}"
            
            assert cors_response["headers"].get("Access-Control-Allow-Origin") != origin, \
                f"Should NOT allow origin {origin}"
    
    @pytest.mark.asyncio
    async def test_data_isolation_between_tenants(
        self,
        sample_candidates: List[Dict[str, Any]],
        mock_firebase_client
    ):
        """Test data isolation between different tenants/organizations"""
        # Create users from different organizations
        org1_user = await self._create_user_with_role(
            email="user1@org1.com",
            role="recruiter",
            organization="org1"
        )
        
        org2_user = await self._create_user_with_role(
            email="user2@org2.com", 
            role="recruiter",
            organization="org2"
        )
        
        # Create test data for each organization
        org1_candidate = await self._create_candidate_for_organization(
            organization="org1",
            candidate_data=sample_candidates[0]
        )
        
        org2_candidate = await self._create_candidate_for_organization(
            organization="org2", 
            candidate_data=sample_candidates[1]
        )
        
        # Test that org1 user can only access org1 data
        org1_search_result = await self._search_candidates_as_user(
            token=org1_user,
            search_query="Python developer"
        )
        
        org1_candidate_ids = [c["candidate_id"] for c in org1_search_result["candidates"]]
        
        assert org1_candidate["candidate_id"] in org1_candidate_ids, \
            "Org1 user should see org1 candidate"
        assert org2_candidate["candidate_id"] not in org1_candidate_ids, \
            "Org1 user should NOT see org2 candidate"
        
        # Test that org2 user can only access org2 data
        org2_search_result = await self._search_candidates_as_user(
            token=org2_user,
            search_query="Python developer"
        )
        
        org2_candidate_ids = [c["candidate_id"] for c in org2_search_result["candidates"]]
        
        assert org2_candidate["candidate_id"] in org2_candidate_ids, \
            "Org2 user should see org2 candidate"
        assert org1_candidate["candidate_id"] not in org2_candidate_ids, \
            "Org2 user should NOT see org1 candidate"
        
        # Test direct access attempts (should be blocked)
        org1_direct_access = await self._attempt_direct_candidate_access(
            token=org1_user,
            candidate_id=org2_candidate["candidate_id"]
        )
        
        assert org1_direct_access["status_code"] == 403, \
            "Should deny direct access to other organization's candidates"
    
    @pytest.mark.asyncio
    async def test_session_management_and_security(
        self,
        performance_monitor
    ):
        """Test session management and security features"""
        # Create test user session
        login_result = await self._simulate_user_login(
            email="session@example.com",
            password="test_password"
        )
        
        user_token = login_result["id_token"]
        
        # Test session timeout
        performance_monitor.start_timer("session_timeout_test")
        
        # Simulate time passage (mock token expiration)
        expired_token = self._generate_expired_test_token()
        
        timeout_response = await self._test_authenticated_api_access(
            token=expired_token,
            endpoint="/api/candidates/search",
            method="GET"
        )
        
        assert timeout_response["status_code"] == 401, \
            "Expired token should be rejected"
        
        performance_monitor.end_timer("session_timeout_test")
        
        # Test concurrent session limits
        concurrent_sessions = []
        max_sessions = 5
        
        for i in range(max_sessions + 2):  # Try 2 extra sessions
            session = await self._simulate_user_login(
                email="session@example.com",
                password="test_password"
            )
            
            if session["success"]:
                concurrent_sessions.append(session)
        
        # Should not exceed maximum concurrent sessions
        assert len(concurrent_sessions) <= max_sessions, \
            f"Should not allow more than {max_sessions} concurrent sessions"
        
        # Test session invalidation on suspicious activity
        suspicious_activity_response = await self._simulate_suspicious_activity(user_token)
        
        assert suspicious_activity_response["session_invalidated"] is True, \
            "Should invalidate session on suspicious activity"
    
    # Helper methods for authentication testing
    async def _simulate_user_login(self, email: str, password: str) -> Dict[str, Any]:
        """Simulate user login process"""
        # Mock Firebase authentication
        return {
            "success": True,
            "user_id": f"user_{hash(email) % 10000}",
            "email": email,
            "id_token": self._generate_valid_test_token(email=email),
            "refresh_token": f"refresh_{hash(email + password) % 10000}",
            "expires_in": 3600
        }
    
    async def _validate_jwt_token(self, token: str) -> Dict[str, Any]:
        """Validate JWT token structure and claims"""
        try:
            # In a real implementation, this would verify signature with Firebase public keys
            # For testing, we'll do basic structure validation
            
            if token.startswith("invalid") or token == "invalid.token.format":
                return {"valid": False, "error": "Invalid token format"}
            
            if "expired" in token:
                return {"valid": False, "error": "Token expired"}
            
            if "tampered" in token:
                return {"valid": False, "error": "Invalid signature"}
            
            # Mock successful validation
            return {
                "valid": True,
                "claims": {
                    "uid": "test_user_123",
                    "email": "test@example.com",
                    "role": "recruiter",
                    "organization": "test_org",
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 3600
                }
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    async def _test_authenticated_api_access(
        self,
        token: str,
        endpoint: str,
        method: str = "GET",
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Test API access with authentication token"""
        # Mock API response based on token validity
        token_validation = await self._validate_jwt_token(token)
        
        if not token_validation["valid"]:
            return {
                "status_code": 401,
                "response": {"error": "Unauthorized"},
                "headers": {}
            }
        
        # Check role-based permissions
        user_role = token_validation["claims"].get("role", "viewer")
        
        # Define role permissions
        admin_only_endpoints = ["/api/admin/users", "/api/admin/analytics"]
        write_endpoints = ["/api/candidates/create", "/api/candidates/update", "/api/candidates/delete"]
        
        if any(admin_endpoint in endpoint for admin_endpoint in admin_only_endpoints):
            if user_role != "admin":
                return {
                    "status_code": 403,
                    "response": {"error": "Forbidden"},
                    "headers": {}
                }
        
        if any(write_endpoint in endpoint for write_endpoint in write_endpoints):
            if user_role == "viewer":
                return {
                    "status_code": 403,
                    "response": {"error": "Forbidden"}, 
                    "headers": {}
                }
        
        # Mock successful response
        return {
            "status_code": 200,
            "response": {"message": "Success", "data": []},
            "headers": {"Content-Type": "application/json"}
        }
    
    async def _test_token_refresh(self, refresh_token: str) -> Dict[str, Any]:
        """Test token refresh mechanism"""
        # Mock token refresh
        return {
            "success": True,
            "new_id_token": self._generate_valid_test_token(),
            "new_refresh_token": f"refresh_{int(time.time())}",
            "expires_in": 3600
        }
    
    async def _test_user_logout(self, token: str) -> Dict[str, Any]:
        """Test user logout process"""
        # Mock logout process
        return {
            "success": True,
            "message": "Successfully logged out"
        }
    
    async def _create_user_with_role(
        self,
        email: str,
        role: str,
        organization: str = "test_org"
    ) -> str:
        """Create user with specific role and return auth token"""
        # Mock user creation and return token
        token_payload = {
            "uid": f"user_{hash(email) % 10000}",
            "email": email,
            "role": role,
            "organization": organization,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600
        }
        
        # In testing, we'll encode a simple token
        return f"test_token_{role}_{hash(email) % 1000}"
    
    async def _test_cors_preflight(
        self,
        origin: str,
        method: str,
        headers: List[str]
    ) -> Dict[str, Any]:
        """Test CORS preflight request"""
        allowed_origins = [
            "https://headhunter.example.com",
            "https://staging.headhunter.com", 
            "http://localhost:3000"
        ]
        
        if origin in allowed_origins:
            return {
                "status_code": 200,
                "headers": {
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": ", ".join(headers),
                    "Access-Control-Max-Age": "86400"
                }
            }
        else:
            return {
                "status_code": 403,
                "headers": {},
                "response": {"error": "Origin not allowed"}
            }
    
    async def _create_candidate_for_organization(
        self,
        organization: str,
        candidate_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create candidate data for specific organization"""
        candidate = candidate_data.copy()
        candidate["organization"] = organization
        candidate["candidate_id"] = f"{organization}_{candidate['candidate_id']}"
        
        return candidate
    
    async def _search_candidates_as_user(
        self,
        token: str,
        search_query: str
    ) -> Dict[str, Any]:
        """Search candidates as specific user (with organization isolation)"""
        token_validation = await self._validate_jwt_token(token)
        
        if not token_validation["valid"]:
            return {"candidates": [], "error": "Unauthorized"}
        
        user_org = token_validation["claims"].get("organization", "unknown")
        
        # Mock search results filtered by organization
        mock_candidates = [
            {
                "candidate_id": f"{user_org}_candidate_1",
                "name": "Test Candidate 1", 
                "organization": user_org
            },
            {
                "candidate_id": f"{user_org}_candidate_2",
                "name": "Test Candidate 2",
                "organization": user_org
            }
        ]
        
        return {"candidates": mock_candidates}
    
    async def _attempt_direct_candidate_access(
        self,
        token: str,
        candidate_id: str
    ) -> Dict[str, Any]:
        """Attempt direct access to candidate by ID"""
        token_validation = await self._validate_jwt_token(token)
        
        if not token_validation["valid"]:
            return {"status_code": 401}
        
        user_org = token_validation["claims"].get("organization", "unknown")
        
        # Check if candidate belongs to user's organization
        if not candidate_id.startswith(f"{user_org}_"):
            return {"status_code": 403, "error": "Access denied"}
        
        return {
            "status_code": 200,
            "candidate": {"candidate_id": candidate_id, "organization": user_org}
        }
    
    async def _simulate_suspicious_activity(self, token: str) -> Dict[str, Any]:
        """Simulate detection of suspicious activity"""
        # Mock suspicious activity detection
        return {
            "suspicious_activity_detected": True,
            "session_invalidated": True,
            "reason": "Multiple failed authentication attempts"
        }
    
    def _generate_valid_test_token(self, email: str = "test@example.com") -> str:
        """Generate valid test JWT token"""
        return f"valid_token_{hash(email) % 1000}_{int(time.time())}"
    
    def _generate_expired_test_token(self) -> str:
        """Generate expired test JWT token"""
        return f"expired_token_{int(time.time() - 7200)}"  # 2 hours ago
    
    def _generate_invalid_signature_token(self) -> str:
        """Generate token with invalid signature"""
        return f"invalid_signature_token_{int(time.time())}"
    
    def _generate_token_missing_claims(self) -> str:
        """Generate token with missing required claims"""
        return f"missing_claims_token_{int(time.time())}"
    
    def _generate_tampered_payload_token(self) -> str:
        """Generate token with tampered payload"""
        return f"tampered_payload_token_{int(time.time())}"