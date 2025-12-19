"""Database utilities for test setup and teardown"""
import uuid
import hashlib
import psycopg2
from typing import Optional, Dict
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "sanad_test"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "testpass")
    )


def create_test_user(
    phone: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    created_by: Optional[str] = None
) -> Dict[str, str]:
    """
    Create a test user in the database.
    
    Args:
        phone: Phone number (E.164 format)
        first_name: User's first name (optional, None for invited-only users)
        last_name: User's last name (optional)
        email: User's email (optional)
        created_by: UUID of the user who invited this user (optional)
    
    Returns:
        Dict with user_id and phone_hash
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        user_id = str(uuid.uuid4())
        phone_hash = hashlib.sha256(phone.encode()).hexdigest()
        
        cursor.execute(
            '''
            INSERT INTO "user" (
                id, phone_hash, phone, first_name, last_name, email, created_by, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            RETURNING id
            ''',
            (user_id, phone_hash, phone if first_name else None, first_name, last_name, email, created_by)
        )
        
        conn.commit()
        print(f"Created test user: {user_id} (phone: {phone})")
        
        return {"user_id": user_id, "phone_hash": phone_hash, "phone": phone}
    
    except Exception as e:
        conn.rollback()
        print(f"Error creating user: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def create_admin_user(phone: str, first_name: str = "Test", last_name: str = "Admin", email: str = "testadmin@test.com") -> Dict[str, str]:
    """
    Create an admin user (both in user and admin tables).
    This creates a fully registered user who is also an admin.
    
    Args:
        phone: Admin phone number
        first_name: Admin first name
        last_name: Admin last name
        email: Admin email
    
    Returns:
        Dict with admin_id and phone
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        admin_id = str(uuid.uuid4())
        phone_hash = hashlib.sha256(phone.encode()).hexdigest()
        
        # Create user record
        cursor.execute(
            '''
            INSERT INTO "user" (
                id, phone_hash, phone, first_name, last_name, email, created_by, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, NULL, NOW(), NOW()
            )
            RETURNING id
            ''',
            (admin_id, phone_hash, phone, first_name, last_name, email)
        )
        
        # Create admin record
        cursor.execute(
            '''
            INSERT INTO admin (
                id, phone, user_id, created_at, updated_at
            ) VALUES (
                %s, %s, %s, NOW(), NOW()
            )
            ''',
            (admin_id, phone, admin_id)
        )
        
        conn.commit()
        print(f"Created admin user: {admin_id} (phone: {phone})")
        
        return {"admin_id": admin_id, "phone": phone, "email": email}
    
    except Exception as e:
        conn.rollback()
        print(f"Error creating admin: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def delete_user_by_phone(phone: str) -> bool:
    """Delete user by phone number (for cleanup)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        phone_hash = hashlib.sha256(phone.encode()).hexdigest()
        
        # First delete from admin table if exists
        cursor.execute('DELETE FROM admin WHERE phone = %s', (phone,))
        
        # Then delete from user table
        cursor.execute('DELETE FROM "user" WHERE phone_hash = %s OR phone = %s', (phone_hash, phone))
        
        conn.commit()
        print(f"Deleted user with phone: {phone}")
        return True
    
    except Exception as e:
        conn.rollback()
        print(f"Error deleting user: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_user_by_phone(phone: str) -> Optional[Dict]:
    """Get user by phone number"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        phone_hash = hashlib.sha256(phone.encode()).hexdigest()
        
        cursor.execute(
            '''
            SELECT id, phone_hash, phone, first_name, last_name, email, created_by, created_at
            FROM "user"
            WHERE phone_hash = %s OR phone = %s
            ''',
            (phone_hash, phone)
        )
        
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "phone_hash": row[1],
                "phone": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "email": row[5],
                "created_by": row[6],
                "created_at": row[7].isoformat() if row[7] else None
            }
        return None
    
    finally:
        cursor.close()
        conn.close()


def cleanup_test_users(phone_prefix: str = "+1555") -> int:
    """
    Cleanup test users by phone prefix.
    This removes all users whose phone starts with the given prefix.

    Args:
        phone_prefix: Phone number prefix to match (default: +1555 for test numbers)

    Returns:
        Number of users deleted
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Delete from admin table first
        cursor.execute('DELETE FROM admin WHERE phone LIKE %s', (f'{phone_prefix}%',))
        admin_count = cursor.rowcount

        # Delete from user table
        cursor.execute('DELETE FROM "user" WHERE phone LIKE %s', (f'{phone_prefix}%',))
        user_count = cursor.rowcount

        conn.commit()
        print(f"Cleaned up {admin_count} admins and {user_count} users with prefix {phone_prefix}")
        return user_count

    except Exception as e:
        conn.rollback()
        print(f"Error during cleanup: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()


# Group-related database utilities

def get_group_by_id(group_id: str) -> Optional[Dict]:
    """Get group by ID from database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM "group" WHERE id = %s', (group_id,))
        row = cursor.fetchone()

        if row:
            return {
                "id": row[0],
                "name": row[1],
                "created_by": row[2],
                "created_at": row[3],
                "updated_at": row[4]
            }
        return None
    finally:
        cursor.close()
        conn.close()


def get_group_members(group_id: str):
    """Get all members of a group"""
    from typing import List, Any

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT ug.id, ug.user_id, u.first_name, u.last_name, u.phone
            FROM user_group ug
            JOIN "user" u ON ug.user_id = u.id
            WHERE ug.group_id = %s
        ''', (group_id,))
        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "user_id": row[1],
                "first_name": row[2],
                "last_name": row[3],
                "phone": row[4]
            }
            for row in rows
        ]
    finally:
        cursor.close()
        conn.close()


def delete_group_by_id(group_id: str) -> bool:
    """Delete group from database (cascade deletes user_group entries)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM "group" WHERE id = %s', (group_id,))
        conn.commit()
        print(f"Deleted group: {group_id}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error deleting group: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def cleanup_test_groups(user_id: str) -> int:
    """Delete all groups created by a user (for cleanup)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM "group" WHERE created_by = %s', (user_id,))
        count = cursor.rowcount
        conn.commit()
        print(f"Cleaned up {count} groups for user {user_id}")
        return count
    except Exception as e:
        conn.rollback()
        print(f"Error during group cleanup: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()
