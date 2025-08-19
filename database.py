import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        """Create and return a database connection"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                deadline TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed BOOLEAN DEFAULT 0,
                completed_at TIMESTAMP
            )
        ''')
        
        # Create reminders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                frequency_type TEXT NOT NULL,
                frequency_value INTEGER NOT NULL,
                start_time TIME,
                end_time TIME,
                escalation_enabled BOOLEAN DEFAULT 0,
                escalation_threshold INTEGER DEFAULT 60,
                custom_messages TEXT,
                last_sent TIMESTAMP,
                next_reminder TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
            )
        ''')
        
        # Create reminder_history table for tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminder_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_type TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_task(self, user_id: int, title: str, description: str, deadline: datetime) -> int:
        """Add a new task to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks (user_id, title, description, deadline)
            VALUES (?, ?, ?, ?)
        ''', (user_id, title, description, deadline))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return task_id
    
    def add_reminder(self, task_id: int, frequency_type: str, frequency_value: int,
                    start_time: Optional[str] = None, end_time: Optional[str] = None,
                    escalation_enabled: bool = False, escalation_threshold: int = 60,
                    custom_messages: Optional[List[str]] = None) -> int:
        """Add a reminder configuration for a task"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        custom_messages_json = json.dumps(custom_messages) if custom_messages else None
        
        cursor.execute('''
            INSERT INTO reminders (task_id, frequency_type, frequency_value, 
                                 start_time, end_time, escalation_enabled, 
                                 escalation_threshold, custom_messages)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, frequency_type, frequency_value, start_time, end_time,
              escalation_enabled, escalation_threshold, custom_messages_json))
        
        reminder_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return reminder_id
    
    def get_user_tasks(self, user_id: int, include_completed: bool = False) -> List[Dict]:
        """Get all tasks for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if include_completed:
            cursor.execute('''
                SELECT * FROM tasks WHERE user_id = ? ORDER BY deadline
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT * FROM tasks WHERE user_id = ? AND completed = 0 ORDER BY deadline
            ''', (user_id,))
        
        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            # Get reminders for this task
            cursor.execute('''
                SELECT * FROM reminders WHERE task_id = ?
            ''', (task['id'],))
            
            reminders = []
            for reminder_row in cursor.fetchall():
                reminder = dict(reminder_row)
                if reminder['custom_messages']:
                    reminder['custom_messages'] = json.loads(reminder['custom_messages'])
                reminders.append(reminder)
            
            task['reminders'] = reminders
            tasks.append(task)
        
        conn.close()
        return tasks
    
    def get_task_by_id(self, task_id: int) -> Optional[Dict]:
        """Get a specific task by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        
        if row:
            task = dict(row)
            # Get reminders
            cursor.execute('SELECT * FROM reminders WHERE task_id = ?', (task_id,))
            reminders = []
            for reminder_row in cursor.fetchall():
                reminder = dict(reminder_row)
                if reminder['custom_messages']:
                    reminder['custom_messages'] = json.loads(reminder['custom_messages'])
                reminders.append(reminder)
            task['reminders'] = reminders
            
            conn.close()
            return task
        
        conn.close()
        return None
    
    def update_task(self, task_id: int, **kwargs) -> bool:
        """Update task fields"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        allowed_fields = ['title', 'description', 'deadline', 'completed', 'completed_at']
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            return False
        
        values.append(task_id)
        query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        success = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return success
    
    def delete_task(self, task_id: int) -> bool:
        """Delete a task and its reminders"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        success = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return success
    
    def update_reminder(self, reminder_id: int, **kwargs) -> bool:
        """Update reminder configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        allowed_fields = ['frequency_type', 'frequency_value', 'start_time', 
                         'end_time', 'escalation_enabled', 'escalation_threshold', 
                         'custom_messages', 'last_sent', 'next_reminder']
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == 'custom_messages' and value is not None:
                    value = json.dumps(value)
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            return False
        
        values.append(reminder_id)
        query = f"UPDATE reminders SET {', '.join(update_fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        success = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return success
    
    def get_pending_reminders(self) -> List[Dict]:
        """Get all tasks that need reminders sent"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all active tasks with their reminders
        cursor.execute('''
            SELECT t.*, r.* 
            FROM tasks t
            JOIN reminders r ON t.id = r.task_id
            WHERE t.completed = 0 
            AND t.deadline > datetime('now')
        ''')
        
        reminders = []
        for row in cursor.fetchall():
            reminder = dict(row)
            if reminder['custom_messages']:
                reminder['custom_messages'] = json.loads(reminder['custom_messages'])
            reminders.append(reminder)
        
        conn.close()
        return reminders
    
    def log_reminder_sent(self, task_id: int, message_type: str = 'normal'):
        """Log that a reminder was sent"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reminder_history (task_id, message_type)
            VALUES (?, ?)
        ''', (task_id, message_type))
        
        conn.commit()
        conn.close()
    
    def get_reminder_history(self, task_id: int) -> List[Dict]:
        """Get reminder history for a task"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM reminder_history 
            WHERE task_id = ? 
            ORDER BY sent_at DESC
        ''', (task_id,))
        
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return history
