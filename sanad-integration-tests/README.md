# Sanad Backend Integration Tests

Python-based integration test suite for the Sanad backend API, validating authentication, invitation flows, and user registration using real HTTP requests and database verification.

---

## 📊 Test Results

**✅ 17/17 Tests Passing (100%)**

- **Authentication Tests** (3/3): Health checks, OTP validation, JWT authentication
- **Invitation Flow Tests** (8/8): User invitations, registration, validation flows
- **Login Flow Tests** (6/6): OTP-based login, profile access, token persistence

---

## 🎯 What This Tests

### Complete User Journey Validation
✅ **Invitation System**: Root user can invite contacts
✅ **Registration Flow**: Invited users can register with OTP
✅ **Login System**: Registered users can login with OTP
✅ **Authentication**: JWT tokens work across authenticated endpoints
✅ **Authorization**: Uninvited users cannot register
✅ **Data Integrity**: Database state matches expected values

### Backend Endpoints Tested
- `GET /health` - Server health check
- `POST /api/v1/user/send-otp` - OTP generation
- `POST /api/v1/user/register` - User registration
- `POST /api/v1/user/login` - User authentication
- `POST /api/v1/user/invite` - Contact invitation
- `GET /api/v1/user/get-auth-user` - Profile retrieval


### Run Tests

```bash
cd sanad-integration-tests

venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pytest -v
```


## 📁 Project Structure

```
sanad-integration-tests/
├── README.md                           # This file
├── QUICK_START.md                      # Practical setup guide
├── TESTING_DOCUMENTATION.md            # Technical deep dive
├── .env                                # Configuration
├── requirements.txt                    # Python dependencies
├── pytest.ini                          # Pytest config
├── conftest.py                         # Shared fixtures
├── src/
│   ├── api_client.py                  # HTTP client for backend
│   └── db_utils.py                    # Database utilities
└── tests/
    ├── test_auth_flow.py              # Authentication tests (3)
    ├── test_invitation_flow.py        # Invitation tests (8)
    └── test_login_flow.py             # Login tests (6)
```

---

### Fixture Flow Example
```python
registered_user fixture:
├── root_user_client (authenticated root user)
├── invited_user (root invites new user)
│   └── Creates user with phone_hash, phone=NULL
├── user_send_otp (invited user requests OTP)
└── user_register (completes registration)
    └── Updates user: phone set, first_name set, returns JWT
```

---



