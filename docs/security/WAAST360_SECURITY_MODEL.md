# WAAST360 Security Model

## Zero Trust Architecture
1. **Bridge Authentication:** The local Bridge must authenticate with the Core API using strong credentials (e.g., JWT, mutual TLS, or long-lived secure tokens).
2. **Immutability:** Audit Events cannot be modified or deleted. 
3. **Data Isolation:** All database queries must be scoped to the `Organization` or `Company` level by default to support multi-tenancy.
4. **Approval Enforcement:** A `Posting Job` cannot be created unless an associated `Approval` record exists, signed by an authorized user.
