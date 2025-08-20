import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_url: Optional[str] = None):
        """Initialize database connection with PostgreSQL"""
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        self.init_database()
    
    def get_connection(self):
        """Create and return a database connection"""
        conn = psycopg2.connect(self.db_url)
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Create tasks table
            cursor.execute('''
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
            
            # Create reminders table
            cursor.execute('''
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
            
            # Create reminder_history table for tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminder_history (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_type VARCHAR(50),
                    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
                )
            ''')
            
            # Create user_task_id_mapping table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_task_id_mapping (
                    user_id BIGINT NOT NULL,
                    user_task_id INTEGER NOT NULL,
                    actual_task_id INTEGER NOT NULL UNIQUE,
                    PRIMARY KEY (user_id, user_task_id),
                    FOREIGN KEY (actual_task_id) REFERENCES tasks (id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_reminders_task_id ON reminders(task_id);
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_reminder_history_task_id ON reminder_history(task_id);
            ''')
            
            conn.commit()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"Error initializing database: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def add_task(self, user_id: int, title: str, description: str, deadline: datetime) -> int:
        """Add a new task and create a user-specific ID mapping."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Add the task to the main tasks table
            cursor.execute('''
                INSERT INTO tasks (user_id, title, description, deadline)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (user_id, title, description, deadline))
            actual_task_id = cursor.fetchone()[0]
            
            # 2. Find the next user_task_id for this user
            cursor.execute(
                "SELECT COALESCE(MAX(user_task_id), 0) + 1 FROM user_task_id_mapping WHERE user_id = %s",
                (user_id,)
            )
            user_task_id = cursor.fetchone()[0]
            
            # 3. Create the mapping
            cursor.execute('''
                INSERT INTO user_task_id_mapping (user_id, user_task_id, actual_task_id)
                VALUES (%s, %s, %s)
            ''', (user_id, user_task_id, actual_task_id))
            
            conn.commit()
            logger.info(f"Task added. UserID: {user_id}, UserTaskID: {user_task_id}, ActualTaskID: {actual_task_id}")
            return user_task_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error adding task with mapping: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def add_reminder(self, task_id: int, frequency_type: str, frequency_value: int,
                    start_time: Optional[str] = None, end_time: Optional[str] = None,
                    escalation_enabled: bool = False, escalation_threshold: int = 60,
                    custom_messages: Optional[List[str]] = None) -> int:
        """Add a reminder configuration for a task"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            custom_messages_json = json.dumps(custom_messages) if custom_messages else None
            
            cursor.execute('''
                INSERT INTO reminders (task_id, frequency_type, frequency_value, 
                                     start_time, end_time, escalation_enabled, 
                                     escalation_threshold, custom_messages)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (task_id, frequency_type, frequency_value, start_time, end_time,
                  escalation_enabled, escalation_threshold, custom_messages_json))
            
            reminder_id = cursor.fetchone()[0]
            conn.commit()
            return reminder_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error adding reminder: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_user_tasks(self, user_id: int, include_completed: bool = False) -> List[Dict]:
        """Get all tasks for a user with their user-facing IDs."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            query = '''
                SELECT t.*, m.user_task_id
                FROM tasks t
                JOIN user_task_id_mapping m ON t.id = m.actual_task_id
                WHERE t.user_id = %s
            '''
            if not include_completed:
                query += " AND t.completed = FALSE"
            query += " ORDER BY t.deadline"
            
            cursor.execute(query, (user_id,))
            
            tasks = []
            for row in cursor.fetchall():
                task = dict(row)
                # Get reminders for this task
                cursor.execute('''
                    SELECT * FROM reminders WHERE task_id = %s
                ''', (task['id'],))
                
                reminders = []
                for reminder_row in cursor.fetchall():
                    reminder = dict(reminder_row)
                    if reminder['custom_messages']:
                        reminder['custom_messages'] = reminder['custom_messages']  # JSONB automatically parsed
                    reminders.append(reminder)
                
                task['reminders'] = reminders
                tasks.append(task)
            
            return tasks
        except Exception as e:
            logger.error(f"Error getting user tasks: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_task_by_id(self, user_id: int, user_task_id: int) -> Optional[Dict]:
        """Get a specific task by its user-facing ID."""
        actual_task_id = self.get_actual_task_id(user_id, user_task_id)
        if not actual_task_id:
            return None
            
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute('''
                SELECT t.*, m.user_task_id
                FROM tasks t
                JOIN user_task_id_mapping m ON t.id = m.actual_task_id
                WHERE t.id = %s AND t.user_id = %s
            ''', (actual_task_id, user_id))
            row = cursor.fetchone()
            
            if row:
                task = dict(row)
                # Get reminders
                cursor.execute('SELECT * FROM reminders WHERE task_id = %s', (actual_task_id,))
                reminders = []
                for reminder_row in cursor.fetchall():
                    reminder = dict(reminder_row)
                    if reminder['custom_messages']:
                        reminder['custom_messages'] = reminder['custom_messages']  # JSONB automatically parsed
                    reminders.append(reminder)
                task['reminders'] = reminders
                
                return task
            
            return None
        except Exception as e:
            logger.error(f"Error getting task by id: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def update_task(self, actual_task_id: int, **kwargs) -> bool:
        """Update task fields using the actual task ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            allowed_fields = ['title', 'description', 'deadline', 'completed', 'completed_at']
            update_fields = []
            values = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    update_fields.append(f"{field} = %s")
                    values.append(value)
            
            if not update_fields:
                return False
            
            values.append(actual_task_id)
            query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = %s"
            
            cursor.execute(query, values)
            success = cursor.rowcount > 0
            
            conn.commit()
            return success
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating task: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def delete_task(self, actual_task_id: int) -> bool:
        """Delete a task and its reminders using the actual task ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # The mapping table will be cleared by the ON DELETE CASCADE foreign key
            cursor.execute('DELETE FROM tasks WHERE id = %s', (actual_task_id,))
            success = cursor.rowcount > 0
            
            conn.commit()
            return success
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting task: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def update_reminder(self, reminder_id: int, **kwargs) -> bool:
        """Update reminder configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            allowed_fields = ['frequency_type', 'frequency_value', 'start_time', 
                             'end_time', 'escalation_enabled', 'escalation_threshold', 
                             'custom_messages', 'last_sent', 'next_reminder']
            update_fields = []
            values = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    if field == 'custom_messages' and value is not None:
                        value = json.dumps(value)
                    update_fields.append(f"{field} = %s")
                    values.append(value)
            
            if not update_fields:
                return False
            
            values.append(reminder_id)
            query = f"UPDATE reminders SET {', '.join(update_fields)} WHERE id = %s"
            
            cursor.execute(query, values)
            success = cursor.rowcount > 0
            
            conn.commit()
            return success
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating reminder: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_pending_reminders(self) -> List[Dict]:
        """Get all tasks that need reminders sent"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Get all active tasks with their reminders
            cursor.execute('''
                SELECT 
                    t.id as task_id,
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
                WHERE t.completed = FALSE 
                AND t.deadline > NOW()
            ''')
            
            reminders = []
            for row in cursor.fetchall():
                reminder = dict(row)
                if reminder['custom_messages']:
                    reminder['custom_messages'] = reminder['custom_messages']  # JSONB automatically parsed
                reminders.append(reminder)
            
            return reminders
        except Exception as e:
            logger.error(f"Error getting pending reminders: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def log_reminder_sent(self, task_id: int, message_type: str = 'normal'):
        """Log that a reminder was sent"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO reminder_history (task_id, message_type)
                VALUES (%s, %s)
            ''', (task_id, message_type))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error logging reminder: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_reminder_history(self, task_id: int) -> List[Dict]:
        """Get reminder history for a task"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute('''
                SELECT * FROM reminder_history 
                WHERE task_id = %s 
                ORDER BY sent_at DESC
            ''', (task_id,))
            
            history = [dict(row) for row in cursor.fetchall()]
            return history
        except Exception as e:
            logger.error(f"Error getting reminder history: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def clear_all_user_data(self, user_id: int) -> int:
        """Clear all data for a user by deleting their tasks, which cascades."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all actual task IDs for the user
            cursor.execute('''
                SELECT t.id FROM tasks t
                JOIN user_task_id_mapping m ON t.id = m.actual_task_id
                WHERE t.user_id = %s
            ''', (user_id,))
            
            tasks_to_delete = [row[0] for row in cursor.fetchall()]
            count = len(tasks_to_delete)
            
            if count > 0:
                # Deleting from tasks table will cascade to mapping, reminders, and history
                cursor.execute('DELETE FROM tasks WHERE id = ANY(%s)', (tasks_to_delete,))
            
            conn.commit()
            logger.info(f"Cleared {count} tasks for user {user_id}.")
            return count
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error clearing user data: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_actual_task_id(self, user_id: int, user_task_id: int) -> Optional[int]:
        """Translate a user-facing ID to an actual database ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT actual_task_id FROM user_task_id_mapping WHERE user_id = %s AND user_task_id = %s",
                (user_id, user_task_id)
            )
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting actual task ID: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def reset_user_task_ids(self, user_id: int) -> bool:
        """
        Alternative approach: Create a user-specific task ID mapping
        This doesn't reset the actual database sequence but provides
        user-friendly task IDs starting from 1
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First, check if we need to create a user_task_mapping table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_task_mapping (
                    user_id BIGINT NOT NULL,
                    user_task_id INTEGER NOT NULL,
                    actual_task_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, user_task_id),
                    FOREIGN KEY (actual_task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
            ''')
            
            # Clear existing mappings for this user
            cursor.execute('DELETE FROM user_task_mapping WHERE user_id = %s', (user_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error resetting user task IDs: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
