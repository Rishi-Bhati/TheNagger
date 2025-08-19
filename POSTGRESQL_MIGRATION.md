# PostgreSQL Migration Summary

This document summarizes the changes made to migrate the Nagger Bot from SQLite to PostgreSQL.

## Changes Made

### 1. Database Module (`database.py`)
- **Replaced SQLite with PostgreSQL** using `psycopg2` library
- **Updated connection method** to use `DATABASE_URL` environment variable
- **Changed SQL syntax** to PostgreSQL:
  - `AUTOINCREMENT` → `SERIAL` for auto-incrementing primary keys
  - `INTEGER` → `BIGINT` for user_id (Telegram user IDs can be large)
  - `TEXT` → `VARCHAR(255)` for fixed-length strings and `TEXT` for variable content
  - `BOOLEAN DEFAULT 0` → `BOOLEAN DEFAULT FALSE`
  - `?` placeholders → `%s` placeholders for parameterized queries
  - `datetime('now')` → `NOW()` for current timestamp
  - Added `RETURNING id` clause for INSERT operations to get the inserted ID
  - Changed from `TEXT` to `JSONB` for storing custom messages (better JSON support)
- **Added proper error handling** with try-except blocks and logging
- **Added database indexes** for better query performance on frequently accessed columns
- **Used `RealDictCursor`** for automatic row-to-dictionary conversion

### 2. Configuration Updates
- **`config.py`**:
  - Added `DATABASE_URL` configuration
  - Removed `DATABASE_NAME` (SQLite specific)
  - Added fallback DATABASE_URL for local development
- **`.env.example`**: Created to show required environment variables

### 3. Dependencies
- **`requirements.txt`**: Added `psycopg2-binary==2.9.9` for PostgreSQL support

### 4. Code Updates
- **`reminder_bot.py`**: Updated to use `DATABASE_URL` instead of `DATABASE_NAME`
- **`reminder_scheduler.py`**: Removed `DATABASE_NAME` import

### 5. Documentation
- **`README.md`**: Updated with PostgreSQL setup instructions and troubleshooting

## PostgreSQL Setup Options

### Local PostgreSQL
```bash
# Install PostgreSQL
sudo apt install postgresql

# Create database
createdb nagger_bot

# Set DATABASE_URL
DATABASE_URL=postgresql://user:password@localhost:5432/nagger_bot
```

### Cloud PostgreSQL Services
- **Railway**: Auto-provisions PostgreSQL with DATABASE_URL
- **Heroku**: Add Heroku Postgres addon
- **Supabase**: Free tier with connection pooling
- **Neon**: Serverless PostgreSQL with generous free tier

## Environment Variables

Create a `.env` file with:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:password@host:port/database_name
```

## Benefits of PostgreSQL

1. **Better scalability** for large datasets
2. **JSONB support** for flexible data storage
3. **Better concurrent access** handling
4. **Cloud hosting compatibility**
5. **Advanced features** like indexes, views, and stored procedures
6. **Better data integrity** with foreign key constraints

## Migration Notes

- The database schema remains largely the same
- All existing functionality is preserved
- The bot automatically creates tables on first run
- No data migration needed for new installations

## Testing

The bot has been tested and runs successfully with PostgreSQL:
- Database tables are created automatically
- All CRUD operations work correctly
- Reminder scheduling functions properly
