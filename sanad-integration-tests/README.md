# Sanad Backend Integration Tests

Python-based integration test suite for the Sanad backend API, validating authentication, invitation flows, and user registration using real HTTP requests and database verification.

---

## 📊 Test Results


- **Authentication Tests** (3/3): Health checks, OTP validation, JWT authentication
- **Invitation Flow Tests** (8/8): User invitations, registration, validation flows
- **Login Flow Tests** (6/6): OTP-based login, profile access, token persistence
- **Group Management Tests** (25/25): Create, add members, delete, view groups

---

## 🎯 What This Tests

### Complete User Journey Validation
✅ **Invitation System**: Root user can invite contacts
✅ **Registration Flow**: Invited users can register with OTP
✅ **Login System**: Registered users can login with OTP
✅ **Authentication**: JWT tokens work across authenticated endpoints
✅ **Authorization**: Uninvited users cannot register
✅ **Group Management**: Create groups, add/remove members, SYNC operations
✅ **Data Integrity**: Database state matches expected values

### Backend Endpoints Tested
- `GET /health` - Server health check
- `POST /api/v1/user/send-otp` - OTP generation
- `POST /api/v1/user/register` - User registration
- `POST /api/v1/user/login` - User authentication
- `POST /api/v1/user/invite` - Contact invitation
- `GET /api/v1/user/get-auth-user` - Profile retrieval

- `POST /api/v1/group/create` - Create new group
- `POST /api/v1/group/add-users` - Add members (SYNC operation)
- `POST /api/v1/group/get-all` - List all groups with pagination
- `POST /api/v1/group/get-users-to-add` - Get contact list for group
- `DELETE /api/v1/group/delete/{id}` - Delete group


### Run Tests

```bash
cd sanad-integration-tests

venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# Run all tests
pytest -v

# Run specific test suites
pytest tests/test_auth_flow.py -v           # Auth tests
pytest tests/test_invitation_flow.py -v     # Invitation tests
pytest tests/test_login_flow.py -v          # Login tests
pytest tests/test_group_flow.py -v          # Group tests 
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
├── docs/
│   ├── GROUP_TESTS_OVERVIEW.md        # Group tests summary
│   └── GROUP_TESTS_DETAILS.md         # Group API details
└── tests/
    ├── test_auth_flow.py              # Authentication tests (3)
    ├── test_invitation_flow.py        # Invitation tests (8)
    ├── test_login_flow.py             # Login tests (6)
    └── test_group_flow.py             # Group management tests (25)
```

---

## 🆕 Group Tests - New Addition

**25 comprehensive tests** covering all group operations:

### What's Tested
- ✅ **Create Groups**: Valid names, duplicate prevention, validation
- ✅ **Add Members**: Registered users, new contacts, mixed additions
- ✅ **SYNC Operation**: Replace member list (not append!)
- ✅ **View Groups**: Pagination, member counts, sorting
- ✅ **Delete Groups**: Cascade deletions, error handling
- ✅ **Contact Integration**: Separate registered vs non-registered users
- ✅ **Edge Cases**: Authentication, empty inputs, invalid IDs

### Key Feature: SYNC Operation
The `add-users` endpoint **replaces** the entire member list:
- Group has [Alice, Bob] → call `add-users` with [Charlie] → Group now has only [Charlie]
- This is tested extensively to ensure correct behavior



### Fixture Flow Example
```python
registered_user fixture:
├── root_user_client (authenticated root user)
├── invited_user (root invites new user)
│   └── Creates user with phone_hash, phone=NULL
├── user_send_otp (invited user requests OTP)
└── user_register (completes registration)
    └── Updates user: phone set, first_name set, returns JWT

test_group fixture (NEW!):
├── registered_user (group owner)
├── group_create (creates test group)
└── group_delete (cleanup after test)
```

---



