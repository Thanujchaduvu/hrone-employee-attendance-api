# Design Decisions

### 1. Indexes
I use indexes to make common lookups faster and to prevent duplicate records where uniqueness is required. The employee code should have a unique index, and attendance records should have an index on employee code and date. I would consider a department-and-date index for analytics, but would add it only if query patterns and performance tests justify the extra write cost.

### 2. Punch-in race
If two identical punch-in requests arrive together, both might check that no record exists. An application-level check alone cannot prevent both from inserting. A unique database index on the attendance identity is needed to allow only one record. The losing request should handle the duplicate-key error and return the response required by the API contract.

### 3. Ties
At the leaderboard cutoff, employees with equal late minutes need deterministic ordering. I would sort by late minutes and then employee code, so repeated requests return a stable list. Whether all tied employees are included or the result is limited strictly to `limit` depends on the API contract.

### 4. Headcount
Department headcount should come from employee records, not attendance logs. This ensures employees with zero attendance logs are still counted.

### 5. Scaling
For 100 times more data, I would review query plans, add only useful indexes, and test aggregation performance with a dataset similar to production.
