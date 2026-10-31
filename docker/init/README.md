# DB bootstrap for Docker users

Compose starts empty Postgres. Load AdventureWorks via
https://github.com/lorint/AdventureWorks-for-Postgres then:

```bash
psql "$DATABASE_URL" -f sql/01_create_wh_views.sql
```

Or run `bash scripts/load_adventureworks.sh`.
