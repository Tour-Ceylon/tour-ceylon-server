# Admin User Promotion

In this phase, admin users are promoted manually via database update.

## Prerequisites

- Direct database access (PostgreSQL)
- User email address
- Admin credentials for your PostgreSQL server

## SQL Command

Run this command in your PostgreSQL client:

```sql
UPDATE "Users" 
SET role = 'admin' 
WHERE email = '<admin-email@example.com>';
```

**Example:**
```sql
UPDATE "Users" 
SET role = 'admin' 
WHERE email = 'alice@company.com';
```

## Verification

Confirm the update worked:

```sql
SELECT id, email, role, created_at 
FROM "Users" 
WHERE email = '<admin-email@example.com>';
```

Expected output: `role` column shows `admin`

## Using pgAdmin or Command Line

### Via pgAdmin (UI)
1. Connect to your database
2. Navigate to `Schemas > public > Tables > Users`
3. Right-click → Query Tool
4. Paste and execute the SQL command above
5. Verify with the verification query

### Via Command Line
```bash
psql -h <host> -U <username> -d <database_name> -c "UPDATE \"Users\" SET role = 'admin' WHERE email = 'alice@company.com';"
```

## Access Admin Portal

After promotion:

1. Sign in to admin portal at `http://localhost:3001` with the promoted admin email
2. You should see the admin dashboard with packages, listings, add-ons, and settings
3. If you still see "Admin access required" error:
   - Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
   - Clear browser cache
   - Try in a private/incognito window

## Troubleshooting

### Issue: Still seeing "Admin access required" error

**Check 1**: Verify the update succeeded
```sql
SELECT role FROM "Users" WHERE email = 'alice@company.com';
```

**Check 2**: Verify email spelling (case-insensitive in database, but double-check)

**Check 3**: Clear Clerk session
- Sign out completely
- Clear all browser cookies/cache
- Sign back in

**Check 4**: Verify DATABASE_URL environment variable
```bash
echo $DATABASE_URL
```

### Issue: Can't connect to database

**Check**: Verify connection details
- Host: `localhost` or your DB hostname
- Port: Usually `5432`
- Database: Check your `.env` file for correct database name
- Username: Verify PostgreSQL user credentials

**Example connection test**:
```bash
psql -h localhost -U postgres -d tour_ceylon_server
```

### Issue: "Users" table not found

**Check**: Run migrations if not done
```bash
alembic upgrade head
```

## Environment Variables

Ensure your `tour-ceylon-server` has correct database setup:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/tour_ceylon_server
CLERK_SECRET_KEY=<your-clerk-secret>
CLERK_ISSUER=<your-clerk-issuer>
```

## Future: Self-Service Promotion

In Phase 2, we'll implement:
- Admin CLI script for role management
- Admin dashboard UI for user role management
- Role-based access control (RBAC) system

For now, manual database updates are the supported method.

---

## Quick Reference

**Promote single admin:**
```sql
UPDATE "Users" SET role = 'admin' WHERE email = 'admin@example.com';
```

**View all admins:**
```sql
SELECT id, email, created_at FROM "Users" WHERE role = 'admin';
```

**Remove admin role (demote to tourist):**
```sql
UPDATE "Users" SET role = 'tourist' WHERE email = 'admin@example.com';
```

**Count total users by role:**
```sql
SELECT role, COUNT(*) FROM "Users" GROUP BY role;
```
