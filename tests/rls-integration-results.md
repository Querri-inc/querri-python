# RLS Integration Test Results

**Date**: 2026-03-10
**SDK**: querri-python-sdk v0.1.0
**Target**: http://localhost (Docker dev stack)
**Test file**: `tests/test_rls_integration.py`

## Test Results: 35/35 PASSED

```
tests/test_rls_integration.py::TestUserManagement::test_01_create_user_1            PASSED
tests/test_rls_integration.py::TestUserManagement::test_02_create_user_2            PASSED
tests/test_rls_integration.py::TestUserManagement::test_03_idempotent_get_or_create PASSED
tests/test_rls_integration.py::TestUserManagement::test_04_list_users               PASSED
tests/test_rls_integration.py::TestUserManagement::test_05_get_user_by_id           PASSED
tests/test_rls_integration.py::TestUserManagement::test_06_update_user              PASSED
tests/test_rls_integration.py::TestAccessPolicyCRUD::test_07_create_policy_single_filter   PASSED
tests/test_rls_integration.py::TestAccessPolicyCRUD::test_08_create_policy_multiple_filters PASSED
tests/test_rls_integration.py::TestAccessPolicyCRUD::test_09_list_policies          PASSED
tests/test_rls_integration.py::TestAccessPolicyCRUD::test_10_get_policy_by_id       PASSED
tests/test_rls_integration.py::TestAccessPolicyCRUD::test_11_update_policy          PASSED
tests/test_rls_integration.py::TestAccessPolicyCRUD::test_12_delete_policy          PASSED
tests/test_rls_integration.py::TestPolicyAssignment::test_13_assign_user_to_policy  PASSED
tests/test_rls_integration.py::TestPolicyAssignment::test_14_remove_user_from_policy PASSED
tests/test_rls_integration.py::TestPolicyAssignment::test_15_replace_all_user_policies PASSED
tests/test_rls_integration.py::TestPolicyAssignment::test_16_verify_assignments     PASSED
tests/test_rls_integration.py::TestGetSessionWorkflow::test_17_get_session_inline_access PASSED
tests/test_rls_integration.py::TestGetSessionWorkflow::test_18_deterministic_policy_naming PASSED
tests/test_rls_integration.py::TestGetSessionWorkflow::test_19_get_session_reuse_policy PASSED
tests/test_rls_integration.py::TestGetSessionWorkflow::test_20_get_session_with_policy_ids PASSED
tests/test_rls_integration.py::TestGetSessionWorkflow::test_21_get_session_no_access PASSED
tests/test_rls_integration.py::TestGetSessionWorkflow::test_22_verify_atomic_replacement PASSED
tests/test_rls_integration.py::TestSessionScopedDataAccess::test_23_create_session  PASSED
tests/test_rls_integration.py::TestSessionScopedDataAccess::test_24_get_source_metadata PASSED
tests/test_rls_integration.py::TestSessionScopedDataAccess::test_25_get_source_data PASSED
tests/test_rls_integration.py::TestSessionScopedDataAccess::test_26_verify_ny_data  PASSED
tests/test_rls_integration.py::TestRLSResolution::test_27_resolve_access            PASSED
tests/test_rls_integration.py::TestRLSResolution::test_28_verify_where_clause       PASSED
tests/test_rls_integration.py::TestAccessControlToggle::test_29_admin_query          PASSED
tests/test_rls_integration.py::TestAccessControlToggle::test_30_no_policies          PASSED
tests/test_rls_integration.py::TestErrorHandling::test_31_invalid_api_key           PASSED
tests/test_rls_integration.py::TestErrorHandling::test_32_expired_session           PASSED
tests/test_rls_integration.py::TestErrorHandling::test_33_policy_not_found          PASSED
tests/test_rls_integration.py::TestCleanup::test_99_cleanup_policies                PASSED
tests/test_rls_integration.py::TestCleanup::test_99_cleanup_users                   PASSED
```

## Bugs Found and Fixed in SDK

### Pre-identified bugs (from bug list)

| ID | File | Description | Fix |
|---|---|---|---|
| CRIT-001 | `querri/types/policy.py` | `Policy.assigned_user_ids` didn't accept `user_ids` alias from API responses | Added `Field(alias="user_ids")` with `populate_by_name=True` model config |
| CRIT-002 | `querri/resources/users.py:187` | `AsyncUsers.list()` missing `async` keyword | Added `async` to method definition |
| HIGH-002 | `querri/resources/embed.py` | `revoke_session(session_id)` vs `refresh_session(session_token)` naming inconsistency | `revoke_session` now accepts both `session_id` (positional, legacy) and `session_token` (keyword, preferred) |

### Bugs discovered during testing

| ID | File | Description | Fix |
|---|---|---|---|
| DISC-001 | `querri/resources/files.py` | `Files.upload()` calls `POST /files/upload` but V1 API endpoint is `POST /files/upload` which returns 501 (Not Implemented). The internal route is `POST /files` with a `filename` header. | Fixed path to `/files` and added `filename` header. Note: V1 file upload endpoint is intentionally 501 -- use `data.create_source()` instead. |
| DISC-002 | `querri/resources/data.py` | Missing `create_source()` and `delete_source()` methods for `POST /data/sources` and `DELETE /data/sources/{id}` V1 endpoints | Added both sync and async methods |
| DISC-003 | `querri/types/policy.py` | `ResolvedAccess.resolved_filters` typed as `List[Dict]` but API returns `{"row_filters": {}, "has_any_policy": bool}` dict | Created `ResolvedFilters` model, added `source_is_access_controlled` and `effective_access` fields to `ResolvedAccess` |

### Server-side issues found (not SDK bugs)

| ID | Description | Impact |
|---|---|---|
| SRV-001 | `POST /data/query` fails with `create_duckdb_connection() got an unexpected keyword argument 'context_name'` | SQL queries via the V1 API are broken. Workaround: use `GET /data/sources/{id}/data` endpoint instead. |
| SRV-002 | `POST /files/upload` (V1) intentionally returns 501 Not Implemented | Cannot upload files via public API. Workaround: use `POST /data/sources` with inline JSON rows. |
| SRV-003 | Sources created via `POST /data/sources` (service="api") don't appear in `GET /data/sources` or `GET /sources` list endpoints | The source is accessible by ID but invisible in listings. May be a service-type filter issue. |

## Files Modified

- `querri/types/policy.py` -- CRIT-001 fix (alias) + DISC-003 fix (ResolvedAccess model)
- `querri/resources/users.py` -- CRIT-002 fix (async keyword)
- `querri/resources/embed.py` -- HIGH-002 fix (dual param naming)
- `querri/resources/files.py` -- DISC-001 fix (upload endpoint path)
- `querri/resources/data.py` -- DISC-002 fix (create_source, delete_source)
- `tests/test_rls_integration.py` -- New integration test file (35 tests)
