# CareHub Appointment Service — Release Requirements v2.4

These are the active release requirements for the CareHub Appointment Service v2.4 release.
ShipSafe AI will validate each requirement against the implementation.

---

## R001

**Cancelled appointments must not generate reminder notifications.**

Acceptance criteria:
- When an appointment's status is `cancelled`, any request to send a reminder notification must be rejected.
- The system must return an appropriate error response.
- No notification record may be persisted for a cancelled appointment.

---

## R002

**Appointment API responses must include `appointment_id`, `status`, and `eta_minutes`.**

Acceptance criteria:
- The `POST /appointments` response body must include the fields `appointment_id`, `status`, and `eta_minutes`.
- The `GET /appointments/<id>` response body must include the fields `appointment_id`, `status`, and `eta_minutes`.
- The `POST /appointments/<id>/cancel` response body must include the fields `appointment_id`, `status`, and `eta_minutes`.

---

## R003

**Appointment priority must be persisted through a versioned database migration.**

Acceptance criteria:
- The `priority` field must be stored in the `appointments` table.
- The field must accept values: `normal`, `high`, `emergency`.
- A versioned migration file must exist in the `migrations/` directory that introduces the `priority` column.
- The priority value submitted at appointment creation must be retrievable via `GET /appointments/<id>`.

---

## R004

**User-controlled database search input must use parameterized database queries.**

Acceptance criteria:
- Any database query that incorporates user-supplied input must use parameterized queries (e.g., `?` placeholders with a values tuple).
- String concatenation or f-string interpolation directly into SQL query text is prohibited.
- This applies to all routes and service functions that accept user input and interact with the database.

---

## R005

**Regression tests must cover cancellation, API contract changes, and appointment priority.**

Acceptance criteria:
- Tests must verify that a cancelled appointment does not trigger a reminder notification (R001).
- Tests must verify that appointment API responses include `appointment_id`, `status`, and `eta_minutes` (R002).
- Tests must verify that appointment priority values are persisted and retrievable (R003).
- All regression tests must be present in the `tests/` directory and must pass.
