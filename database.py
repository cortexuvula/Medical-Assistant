import sqlite3
import os
import datetime

class Database:
    def __init__(self, db_path="database.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establish connection to the database"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
    def disconnect(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            
    def create_tables(self):
        """Create the recordings table if it doesn't exist"""
        self.connect()
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            transcript TEXT,
            soap_note TEXT,
            referral TEXT,
            letter TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        self.conn.commit()
        self.disconnect()
    
    def add_recording(self, filename, transcript=None, soap_note=None, referral=None, letter=None):
        """Add a new recording to the database
        
        Parameters:
        - filename: Path to the recording file
        - transcript: Text transcript of the recording
        - soap_note: Generated SOAP note
        - referral: Generated referral
        - letter: Generated letter
        
        Returns:
        - ID of the new recording
        """
        self.connect()
        self.cursor.execute('''
        INSERT INTO recordings (filename, transcript, soap_note, referral, letter, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (filename, transcript, soap_note, referral, letter, datetime.datetime.now()))
        row_id = self.cursor.lastrowid
        self.conn.commit()
        self.disconnect()
        return row_id
    
    def update_recording(self, recording_id, **kwargs):
        """
        Update a recording in the database
        
        Parameters:
        - recording_id: ID of the recording to update
        - kwargs: Fields to update (filename, transcript, soap_note, referral, letter)
        
        Returns:
        - True if successful, False otherwise
        """
        allowed_fields = ['filename', 'transcript', 'soap_note', 'referral', 'letter']
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            return False
        
        self.connect()
        query = "UPDATE recordings SET "
        query += ", ".join([f"{field} = ?" for field in update_fields.keys()])
        query += " WHERE id = ?"
        
        values = list(update_fields.values())
        values.append(recording_id)
        
        self.cursor.execute(query, values)
        rows_affected = self.cursor.rowcount
        self.conn.commit()
        self.disconnect()
        
        return rows_affected > 0
    
    def delete_recording(self, recording_id):
        """
        Delete a recording from the database
        
        Parameters:
        - recording_id: ID of the recording to delete
        
        Returns:
        - True if successful, False otherwise
        """
        self.connect()
        self.cursor.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
        rows_affected = self.cursor.rowcount
        self.conn.commit()
        self.disconnect()
        
        return rows_affected > 0
    
    def get_recording(self, recording_id):
        """Get a recording by ID"""
        self.connect()
        self.cursor.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,))
        recording = self.cursor.fetchone()
        self.disconnect()
        
        if recording:
            columns = ['id', 'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
            return dict(zip(columns, recording))
        return None
    
    def get_all_recordings(self):
        """Get all recordings"""
        self.connect()
        self.cursor.execute("SELECT * FROM recordings ORDER BY timestamp DESC")
        recordings = self.cursor.fetchall()
        self.disconnect()
        
        columns = ['id', 'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
        return [dict(zip(columns, recording)) for recording in recordings]
        
    def search_recordings(self, search_term):
        """Search for recordings containing the search term in any text field
        
        Parameters:
        - search_term: Text to search for in filename, transcript, soap_note, referral, or letter
        
        Returns:
        - List of matching recordings
        """
        self.connect()
        query = """SELECT * FROM recordings 
                 WHERE filename LIKE ? 
                 OR transcript LIKE ? 
                 OR soap_note LIKE ? 
                 OR referral LIKE ? 
                 OR letter LIKE ? 
                 ORDER BY timestamp DESC"""
        search_pattern = f"%{search_term}%"
        params = (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern)
        
        self.cursor.execute(query, params)
        recordings = self.cursor.fetchall()
        self.disconnect()
        
        columns = ['id', 'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
        return [dict(zip(columns, recording)) for recording in recordings]
    
    def get_recordings_by_date_range(self, start_date, end_date):
        """Get recordings created within a date range
        
        Parameters:
        - start_date: Start date (datetime object or ISO format string)
        - end_date: End date (datetime object or ISO format string)
        
        Returns:
        - List of recordings within the date range
        """
        if isinstance(start_date, str):
            start_date = datetime.datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.datetime.fromisoformat(end_date)
            
        # Add one day to end_date to make the range inclusive
        end_date = end_date + datetime.timedelta(days=1)
        
        self.connect()
        self.cursor.execute(
            "SELECT * FROM recordings WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC",
            (start_date.isoformat(), end_date.isoformat())
        )
        recordings = self.cursor.fetchall()
        self.disconnect()
        
        columns = ['id', 'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
        return [dict(zip(columns, recording)) for recording in recordings]
