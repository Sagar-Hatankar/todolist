"""Improved Streamlit To-Do & Diary Application - Backward Compatible Version"""

import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from contextlib import contextmanager

# Database Management with backward compatibility
class DatabaseManager:
    def __init__(self, db_name: str = "data.db"):
        self.db_name = db_name
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check existing schema
            cursor.execute("PRAGMA table_info(todos)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            if not existing_columns:
                # Create new table
                cursor.execute('''
                    CREATE TABLE todos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task TEXT NOT NULL,
                        priority TEXT,
                        due_date TEXT,
                        status TEXT NOT NULL,
                        category TEXT DEFAULT 'General'
                    )
                ''')
            else:
                # Add category column if it doesn't exist
                if 'category' not in existing_columns:
                    try:
                        cursor.execute('ALTER TABLE todos ADD COLUMN category TEXT DEFAULT "General"')
                    except sqlite3.Error:
                        pass
            
            # Diary table (same as original)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS diary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_date TEXT NOT NULL UNIQUE,
                    entry_text TEXT NOT NULL,
                    mood TEXT DEFAULT ''
                )
            ''')
            
            # Add mood column if it doesn't exist
            cursor.execute("PRAGMA table_info(diary)")
            diary_columns = [column[1] for column in cursor.fetchall()]
            if 'mood' not in diary_columns:
                try:
                    cursor.execute('ALTER TABLE diary ADD COLUMN mood TEXT DEFAULT ""')
                except sqlite3.Error:
                    pass
            
            conn.commit()
    
    def add_task(self, task, priority, due_date, category='General'):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO todos (task, priority, due_date, status, category) VALUES (?, ?, ?, ?, ?)",
                    (task, priority, due_date, 'Pending', category)
                )
                conn.commit()
                return True
        except sqlite3.Error:
            return False
    
    def get_tasks(self, status_filter='All', category_filter='All'):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if category column exists
            cursor.execute("PRAGMA table_info(todos)")
            columns = [column[1] for column in cursor.fetchall()]
            has_category = 'category' in columns
            
            if status_filter == 'All' and (category_filter == 'All' or not has_category):
                cursor.execute("SELECT * FROM todos ORDER BY id DESC")
            elif status_filter != 'All' and (category_filter == 'All' or not has_category):
                cursor.execute("SELECT * FROM todos WHERE status = ? ORDER BY id DESC", (status_filter,))
            elif status_filter == 'All' and has_category:
                cursor.execute("SELECT * FROM todos WHERE category = ? ORDER BY id DESC", (category_filter,))
            elif has_category:
                cursor.execute("SELECT * FROM todos WHERE status = ? AND category = ? ORDER BY id DESC", 
                             (status_filter, category_filter))
            
            return cursor.fetchall()
    
    def update_task_status(self, task_id, new_status):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE todos SET status = ? WHERE id = ?", (new_status, task_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error:
            return False
    
    def delete_task(self, task_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM todos WHERE id = ?", (task_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error:
            return False
    
    def get_task_stats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM todos")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM todos WHERE status = 'Completed'")
            completed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM todos WHERE status = 'Pending' AND due_date < date('now')")
            overdue = cursor.fetchone()[0]
            
            return {
                'total': total,
                'completed': completed,
                'pending': total - completed,
                'overdue': overdue,
                'completion_rate': (completed / total * 100) if total > 0 else 0
            }
    
    def upsert_diary_entry(self, entry_date, entry_text, mood=''):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if mood column exists
                cursor.execute("PRAGMA table_info(diary)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'mood' in columns:
                    cursor.execute(
                        "INSERT OR REPLACE INTO diary (entry_date, entry_text, mood) VALUES (?, ?, ?)",
                        (entry_date, entry_text, mood)
                    )
                else:
                    cursor.execute(
                        "INSERT OR REPLACE INTO diary (entry_date, entry_text) VALUES (?, ?)",
                        (entry_date, entry_text)
                    )
                conn.commit()
                return True
        except sqlite3.Error:
            return False
    
    def get_diary_entry(self, entry_date):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM diary WHERE entry_date = ?", (entry_date,))
            return cursor.fetchone()

# Utility functions
def get_priority_emoji(priority):
    return {'High': '🔴', 'Medium': '🟡', 'Low': '🟢'}.get(priority, '⚪')

def get_mood_emoji(mood):
    moods = {
        'Happy': '😊', 'Sad': '😢', 'Excited': '🤩', 'Calm': '😌',
        'Stressed': '😰', 'Angry': '😠', 'Grateful': '🙏', 'Tired': '😴'
    }
    return moods.get(mood, '😐')

def calculate_days_until(due_date):
    try:
        due = datetime.strptime(due_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        return (due - today).days
    except:
        return 0

@st.cache_resource
def init_database():
    return DatabaseManager()

def main():
    st.set_page_config(
        page_title="Todo & Diary",
        page_icon="📝",
        layout="wide"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 10px;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
        }
        .task-card {
            border: 1px solid #e1e4e8;
            border-radius: 8px;
            padding: 1rem;
            margin: 0.5rem 0;
            background: #f8f9fa;
        }
        .overdue { border-left: 4px solid #e74c3c; }
        .due-today { border-left: 4px solid #f39c12; }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize database
    db_manager = init_database()
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📝 Todo & Diary</h1>
        <p>Improved productivity app with better features</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar stats
    with st.sidebar:
        st.markdown("### 🎯 Quick Stats")
        stats = db_manager.get_task_stats()
        
        st.metric("Total Tasks", stats['total'])
        st.metric("Completed", stats['completed'])
        st.metric("Completion Rate", f"{stats['completion_rate']:.1f}%")
        
        if stats['overdue'] > 0:
            st.error(f"⚠️ {stats['overdue']} overdue tasks!")
        else:
            st.success("✅ No overdue tasks!")
    
    # Tabs
    tab1, tab2 = st.tabs(["📋 Tasks", "📖 Diary"])
    
    # Tasks Tab
    with tab1:
        st.header("Task Management")
        
        # Add task form
        with st.form("add_task", clear_on_submit=True):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                task = st.text_input("Task Description*", placeholder="Enter your task...")
            
            with col2:
                priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
            
            col3, col4 = st.columns(2)
            with col3:
                due_date = st.date_input("Due Date", min_value=datetime.today())
            with col4:
                categories = ["General", "Work", "Personal", "Health", "Learning"]
                category = st.selectbox("Category", categories)
            
            submitted = st.form_submit_button("➕ Add Task", type="primary")
            
            if submitted and task:
                if db_manager.add_task(task, priority, due_date.strftime('%Y-%m-%d'), category):
                    st.success("✅ Task added successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to add task")
        
        st.markdown("---")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("Status", ["All", "Pending", "Completed"])
        with col2:
            category_filter = st.selectbox("Filter by Category", ["All", "General", "Work", "Personal", "Health", "Learning"])
        with col3:
            search = st.text_input("🔍 Search tasks")
        
        # Display tasks
        tasks = db_manager.get_tasks(status_filter, category_filter)
        
        if search:
            tasks = [task for task in tasks if search.lower() in task['task'].lower()]
        
        if not tasks:
            st.info("📝 No tasks found!")
        else:
            # Export button
            if st.button("📄 Export to CSV"):
                df = pd.DataFrame([dict(task) for task in tasks])
                csv = df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    f"tasks_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )
            
            # Task list
            for task in tasks:
                task_dict = dict(task)
                
                # Safe field access
                task_id = task_dict['id']
                task_text = task_dict['task']
                priority = task_dict.get('priority', 'Medium')
                due_date = task_dict.get('due_date', '')
                status = task_dict.get('status', 'Pending')
                category = task_dict.get('category', 'General')
                
                is_completed = status == 'Completed'
                
                # Determine urgency
                css_class = ""
                if due_date:
                    days_until = calculate_days_until(due_date)
                    if days_until < 0:
                        css_class = "overdue"
                    elif days_until == 0:
                        css_class = "due-today"
                
                container = st.container(border=True)
                
                with container:
                    col1, col2, col3 = st.columns([1, 6, 1])
                    
                    with col1:
                        new_status = st.checkbox("", value=is_completed, key=f"task_{task_id}")
                        if new_status != is_completed:
                            status_text = 'Completed' if new_status else 'Pending'
                            if db_manager.update_task_status(task_id, status_text):
                                st.rerun()
                    
                    with col2:
                        priority_emoji = get_priority_emoji(priority)
                        
                        if is_completed:
                            st.markdown(f"<del>{priority_emoji} {task_text}</del>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{priority_emoji} {task_text}**")
                        
                        # Task info
                        info_parts = []
                        if due_date:
                            days_until = calculate_days_until(due_date)
                            if days_until < 0:
                                info_parts.append(f"🔥 Overdue by {abs(days_until)} days")
                            elif days_until == 0:
                                info_parts.append("📅 Due today")
                            else:
                                info_parts.append(f"📅 Due in {days_until} days")
                        
                        info_parts.append(f"📂 {category}")
                        st.caption(" • ".join(info_parts))
                    
                    with col3:
                        if st.button("🗑️", key=f"del_{task_id}"):
                            if db_manager.delete_task(task_id):
                                st.rerun()
    
    # Diary Tab
    with tab2:
        st.header("Daily Journal")
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_entry = db_manager.get_diary_entry(today_str)
        
        st.subheader(f"📅 Today's Entry - {datetime.now().strftime('%B %d, %Y')}")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            entry_text = st.text_area(
                "What's on your mind?",
                value=today_entry['entry_text'] if today_entry else "",
                height=200,
                placeholder="Write about your day..."
            )
        
        with col2:
            moods = ['', 'Happy', 'Sad', 'Excited', 'Calm', 'Stressed', 'Angry', 'Grateful', 'Tired']
            current_mood = today_entry['mood'] if today_entry and 'mood' in today_entry.keys() else ''
            mood = st.selectbox("Today's Mood", moods, 
                               index=moods.index(current_mood) if current_mood in moods else 0)
        
        if st.button("💾 Save Entry", type="primary"):
            if entry_text.strip():
                if db_manager.upsert_diary_entry(today_str, entry_text, mood):
                    st.success("✅ Entry saved!")
                    st.rerun()
                else:
                    st.error("❌ Failed to save entry")
            else:
                st.warning("⚠️ Please write something first")
        
        st.markdown("---")
        
        # View past entry
        st.subheader("📖 View Past Entry")
        selected_date = st.date_input("Select date", max_value=datetime.today())
        
        if selected_date:
            date_str = selected_date.strftime('%Y-%m-%d')
            past_entry = db_manager.get_diary_entry(date_str)
            
            if past_entry:
                st.info(f"**Entry for {selected_date.strftime('%B %d, %Y')}:**")
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(past_entry['entry_text'])
                with col2:
                    if 'mood' in past_entry.keys() and past_entry['mood']:
                        mood_emoji = get_mood_emoji(past_entry['mood'])
                        st.caption(f"Mood: {mood_emoji} {past_entry['mood']}")
            else:
                st.warning(f"No entry found for {selected_date.strftime('%B %d, %Y')}")

if __name__ == '__main__':
    main()