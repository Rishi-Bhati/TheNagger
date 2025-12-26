import asyncpg
import logging
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_url: Optional[str] = None):
        """Initialize database configuration"""
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        self.pool = None

    async def connect(self):
        """Initialize the connection pool"""
        if not self.pool:
            try:
                # Optimized pool settings for low-resource environment (512MB RAM)
                # min_size=1: Keep one connection alive
                # max_size=10: Cap at 10 to avoid OOM, but enough for concurrency
                # max_inactive_connection_lifetime: Close unused connections after 300s
                # statement_cache_size=0: Disable prepared statements for PgBouncer compatibility
                self.pool = await asyncpg.create_pool(
                    self.db_url,
                    min_size=1,
                    max_size=10, 
                    max_inactive_connection_lifetime=300,
                    statement_cache_size=0
                )
                logger.info("Database connection pool created")
                await self.init_database()
            except Exception as e:
                logger.error(f"Failed to create database pool: {e}")
                raise

    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def acquire_connection(self):
        """Yield a database connection from the pool"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            yield conn
            
    async def init_database(self):
        """Initialize database tables"""
        async with self.acquire_connection() as conn:
            async with conn.transaction():
                # tasks table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        deadline TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed BOOLEAN DEFAULT FALSE,
                        completed_at TIMESTAMP
                    )
                ''')
                
                # reminders table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS reminders (
                        id SERIAL PRIMARY KEY,
                        task_id INTEGER NOT NULL,
                        frequency_type VARCHAR(50) NOT NULL,
                        frequency_value INTEGER NOT NULL,
                        start_time TIME,
                        end_time TIME,
                        escalation_enabled BOOLEAN DEFAULT FALSE,
                        escalation_threshold INTEGER DEFAULT 60,
                        custom_messages JSONB,
                        last_sent TIMESTAMP,
                        next_reminder TIMESTAMP,
                        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
                    )
                ''')
                
                # reminder_history table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS reminder_history (
                        id SERIAL PRIMARY KEY,
                        task_id INTEGER NOT NULL,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        message_type VARCHAR(50),
                        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
                    )
                ''')
                
                # user_task_id_mapping table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_task_id_mapping (
                        user_id BIGINT NOT NULL,
                        user_task_id INTEGER NOT NULL,
                        actual_task_id INTEGER NOT NULL UNIQUE,
                        PRIMARY KEY (user_id, user_task_id),
                        FOREIGN KEY (actual_task_id) REFERENCES tasks (id) ON DELETE CASCADE
                    )
                ''')
                
                # users table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        full_name VARCHAR(255),
                        timezone VARCHAR(50) DEFAULT 'UTC',
                        status VARCHAR(50) DEFAULT 'active',
                        last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # bot_errors table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS bot_errors (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        error_type VARCHAR(100),
                        error_message TEXT,
                        stack_trace TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # bot_metrics table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS bot_metrics (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        command VARCHAR(100),
                        processing_time_ms FLOAT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Indexes for performance
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_reminders_task_id ON reminders(task_id)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_reminder_history_task_id ON reminder_history(task_id)')
                
                # Migration: Ensure new columns exist
                try:
                    await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(255)')
                    await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)')
                    await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                except Exception:
                    pass # Ignore if already exists/fails safely

        logger.info("Database tables initialized successfully")

    async def add_task(self, user_id: int, title: str, description: str, deadline: datetime) -> int:
        """Add a new task and create a user-specific ID mapping."""
        async with self.acquire_connection() as conn:
            async with conn.transaction():
                # 1. Add task
                actual_task_id = await conn.fetchval('''
                    INSERT INTO tasks (user_id, title, description, deadline)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                ''', user_id, title, description, deadline)
                
                # 2. Get next user_task_id
                user_task_id = await conn.fetchval(
                    "SELECT COALESCE(MAX(user_task_id), 0) + 1 FROM user_task_id_mapping WHERE user_id = $1",
                    user_id
                )
                
                # 3. Create mapping
                await conn.execute('''
                    INSERT INTO user_task_id_mapping (user_id, user_task_id, actual_task_id)
                    VALUES ($1, $2, $3)
                ''', user_id, user_task_id, actual_task_id)
                
                logger.info(f"Task added using asyncpg: UserID {user_id}, ID {user_task_id}")
                return user_task_id

    async def add_reminder(self, task_id: int, frequency_type: str, frequency_value: int,
                    start_time: Optional[str] = None, end_time: Optional[str] = None,
                    escalation_enabled: bool = False, escalation_threshold: int = 60,
                    custom_messages: Optional[List[str]] = None) -> int:
        """Add a reminder configuration for a task"""
        # Convert times to specific types if needed, string is usually fine for Postgres TIME type via asyncpg if format is correct
        # Ensure custom_messages is json string or pass as list if we change column type to jsonb (asyncpg handles conversion automatically for jsonb if list is passed? usually needs json.dumps for text)
        # However, our table def says JSONB. Asyncpg can encode dict/list to JSONB automatically if codec is set, but default behavior:
        # We should pass string for JSONB or use set_type_codec. Safest is json.dumps.
        
        custom_messages_json = json.dumps(custom_messages) if custom_messages else None
        
        # Parse time strings to time objects if necessary, but Postgres keeps them as Time.
        # asyncpg prefers datetime.time objects for TIME columns.
        def parse_time_str(t_str):
            if not t_str: return None
            try:
                return datetime.strptime(t_str, '%H:%M').time()
            except ValueError:
                return None # Or handle error

        start_time_obj = parse_time_str(start_time)
        end_time_obj = parse_time_str(end_time)

        async with self.acquire_connection() as conn:
            reminder_id = await conn.fetchval('''
                INSERT INTO reminders (task_id, frequency_type, frequency_value, 
                                     start_time, end_time, escalation_enabled, 
                                     escalation_threshold, custom_messages)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            ''', task_id, frequency_type, frequency_value, start_time_obj, end_time_obj,
                escalation_enabled, escalation_threshold, custom_messages_json)
            return reminder_id

    async def get_user_tasks(self, user_id: int, include_completed: bool = False) -> List[Dict]:
        """Get all tasks for a user efficiently."""
        async with self.acquire_connection() as conn:
            # 1. Get tasks
            query = '''
                SELECT t.*, m.user_task_id
                FROM tasks t
                JOIN user_task_id_mapping m ON t.id = m.actual_task_id
                WHERE t.user_id = $1
            '''
            if not include_completed:
                query += " AND t.completed = FALSE"
            query += " ORDER BY t.deadline"
            
            rows = await conn.fetch(query, user_id)
            tasks = [dict(row) for row in rows]
            
            if not tasks:
                return []
                
            task_ids = [t['id'] for t in tasks]
            
            # 2. Get reminders
            reminders_rows = await conn.fetch('''
                SELECT * FROM reminders WHERE task_id = ANY($1::int[])
            ''', task_ids)
            
            reminders_by_task = {}
            for r in reminders_rows:
                r_dict = dict(r)
                if r_dict['custom_messages']:
                    try:
                        r_dict['custom_messages'] = json.loads(r_dict['custom_messages'])
                    except:
                        pass
                        
                # Convert time objects back to string for consistency with app logic
                if r_dict.get('start_time'):
                    r_dict['start_time'] = r_dict['start_time'].strftime('%H:%M')
                if r_dict.get('end_time'):
                    r_dict['end_time'] = r_dict['end_time'].strftime('%H:%M')
                    
                tid = r_dict['task_id']
                if tid not in reminders_by_task:
                    reminders_by_task[tid] = []
                reminders_by_task[tid].append(r_dict)
            
            for task in tasks:
                task['reminders'] = reminders_by_task.get(task['id'], [])
            
            return tasks

    async def get_task_by_id(self, user_id: int, user_task_id: int) -> Optional[Dict]:
        """Get a specific task by its user-facing ID."""
        actual_task_id = await self.get_actual_task_id(user_id, user_task_id)
        if not actual_task_id:
            return None
            
        async with self.acquire_connection() as conn:
            row = await conn.fetchrow('''
                SELECT t.*, m.user_task_id
                FROM tasks t
                JOIN user_task_id_mapping m ON t.id = m.actual_task_id
                WHERE t.id = $1 AND t.user_id = $2
            ''', actual_task_id, user_id)
            
            if row:
                task = dict(row)
                reminders_rows = await conn.fetch('SELECT * FROM reminders WHERE task_id = $1', actual_task_id)
                reminders = []
                for r in reminders_rows:
                    rem = dict(r)
                    if rem['custom_messages']:
                         try:
                            rem['custom_messages'] = json.loads(rem['custom_messages'])
                         except:
                            pass
                    
                    if rem.get('start_time'):
                        rem['start_time'] = rem['start_time'].strftime('%H:%M')
                    if rem.get('end_time'):
                        rem['end_time'] = rem['end_time'].strftime('%H:%M')
                        
                    reminders.append(rem)
                task['reminders'] = reminders
                return task
            return None

    async def update_task(self, actual_task_id: int, **kwargs) -> bool:
        """Update task fields."""
        allowed_fields = ['title', 'description', 'deadline', 'completed', 'completed_at']
        update_fields = []
        values = []
        
        for idx, (field, value) in enumerate(kwargs.items()):
            if field in allowed_fields:
                update_fields.append(f"{field} = ${idx + 2}")
                values.append(value)
        
        if not update_fields:
            return False
            
        query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = $1"
        
        async with self.acquire_connection() as conn:
            result = await conn.execute(query, actual_task_id, *values)
            # result string format is like "UPDATE 1"
            return "UPDATE 0" not in result

    async def delete_task(self, actual_task_id: int) -> bool:
        """Delete a task."""
        async with self.acquire_connection() as conn:
            result = await conn.execute('DELETE FROM tasks WHERE id = $1', actual_task_id)
            return "DELETE 0" not in result

    async def update_reminder(self, reminder_id: int, **kwargs) -> bool:
        """Update reminder configuration."""
        allowed_fields = ['frequency_type', 'frequency_value', 'start_time', 
                         'end_time', 'escalation_enabled', 'escalation_threshold', 
                         'custom_messages', 'last_sent', 'next_reminder']
        update_fields = []
        values = []
        
        i = 2
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == 'custom_messages' and value is not None:
                     value = json.dumps(value)
                update_fields.append(f"{field} = ${i}")
                values.append(value)
                i += 1
                
        if not update_fields:
            return False
            
        query = f"UPDATE reminders SET {', '.join(update_fields)} WHERE id = $1"
        
        async with self.acquire_connection() as conn:
            result = await conn.execute(query, reminder_id, *values)
            return "UPDATE 0" not in result

    async def get_pending_reminders(self) -> List[Dict]:
        """Get all pending reminders."""
        async with self.acquire_connection() as conn:
            rows = await conn.fetch('''
                SELECT 
                    t.id as task_id,
                    m.user_task_id,
                    t.user_id,
                    t.title,
                    t.description,
                    t.deadline,
                    t.created_at,
                    t.completed,
                    r.id as reminder_id,
                    r.frequency_type,
                    r.frequency_value,
                    r.start_time,
                    r.end_time,
                    r.escalation_enabled,
                    r.escalation_threshold,
                    r.custom_messages,
                    r.last_sent,
                    r.next_reminder
                FROM tasks t
                JOIN reminders r ON t.id = r.task_id
                JOIN user_task_id_mapping m ON t.id = m.actual_task_id
                WHERE t.completed = FALSE 
                AND t.deadline > NOW()
            ''')
            
            reminders = []
            for row in rows:
                reminder = dict(row)
                if reminder['custom_messages']:
                     try:
                        reminder['custom_messages'] = json.loads(reminder['custom_messages'])
                     except:
                        pass
                # Convert active times to datetime object for processing if needed or check types
                # Postgres via asyncpg returns datetime.time for TIME columns. 
                reminders.append(reminder)
            return reminders

    async def log_reminder_sent(self, task_id: int, message_type: str = 'normal'):
        """Log that a reminder was sent"""
        async with self.acquire_connection() as conn:
            await conn.execute('''
                INSERT INTO reminder_history (task_id, message_type)
                VALUES ($1, $2)
            ''', task_id, message_type)

    async def get_reminder_history(self, task_id: int) -> List[Dict]:
        async with self.acquire_connection() as conn:
             rows = await conn.fetch('''
                SELECT * FROM reminder_history 
                WHERE task_id = $1 
                ORDER BY sent_at DESC
            ''', task_id)
             return [dict(r) for r in rows]

    async def clear_all_user_data(self, user_id: int) -> int:
        """Clear all data for a user."""
        async with self.acquire_connection() as conn:
            # 1. Get task IDs
            rows = await conn.fetch('''
                SELECT t.id FROM tasks t
                WHERE t.user_id = $1
            ''', user_id)
            tasks_to_delete = [r['id'] for r in rows]
            
            if not tasks_to_delete:
                return 0
                
            # 2. Delete tasks (cascades)
            # asyncpg requires ANY($1::int[]) for array matching
            await conn.execute('DELETE FROM tasks WHERE id = ANY($1::int[])', tasks_to_delete)
            return len(tasks_to_delete)

    async def get_actual_task_id(self, user_id: int, user_task_id: int) -> Optional[int]:
        """Translate user-facing ID to actual ID."""
        async with self.acquire_connection() as conn:
            val = await conn.fetchval(
                "SELECT actual_task_id FROM user_task_id_mapping WHERE user_id = $1 AND user_task_id = $2",
                user_id, user_task_id
            )
            return val

    async def set_user_timezone(self, user_id: int, timezone: str) -> bool:
        """Set user timezone."""
        async with self.acquire_connection() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, timezone)
                VALUES ($1, $2)
                ON CONFLICT (user_id) 
                DO UPDATE SET timezone = EXCLUDED.timezone
            ''', user_id, timezone)
            return True

    async def get_user_timezone(self, user_id: int) -> str:
        """Get user timezone."""
        async with self.acquire_connection() as conn:
            val = await conn.fetchval('SELECT timezone FROM users WHERE user_id = $1', user_id)
            return val or 'UTC'

    async def log_bot_error(self, user_id: Optional[int], error_type: str, error_message: str, stack_trace: str):
        """Log critical bot error."""
        try:
            async with self.acquire_connection() as conn:
                await conn.execute('''
                    INSERT INTO bot_errors (user_id, error_type, error_message, stack_trace)
                    VALUES ($1, $2, $3, $4)
                ''', user_id, error_type, error_message, stack_trace)
        except Exception as e:
            logger.error(f"Failed to log bot error: {e}")

    async def log_bot_metric(self, user_id: int, command: str, processing_time_ms: float):
        """Log performance metric."""
        try:
            async with self.acquire_connection() as conn:
                await conn.execute('''
                    INSERT INTO bot_metrics (user_id, command, processing_time_ms)
                    VALUES ($1, $2, $3)
                ''', user_id, command, processing_time_ms)
        except Exception:
            pass # Non-critical

    async def update_user_activity(self, user_id: int, username: Optional[str] = None, full_name: Optional[str] = None):
        """Update user activity timestamp."""
        try:
             async with self.acquire_connection() as conn:
                await conn.execute('''
                    INSERT INTO users (user_id, username, full_name, last_active_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        last_active_at = CURRENT_TIMESTAMP,
                        username = COALESCE(EXCLUDED.username, users.username),
                        full_name = COALESCE(EXCLUDED.full_name, users.full_name)
                ''', user_id, username, full_name)
        except Exception as e:
            logger.error(f"Failed to update user activity: {e}")
