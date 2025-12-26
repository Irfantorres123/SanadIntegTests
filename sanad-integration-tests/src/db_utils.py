"""Database utilities for test setup and teardown"""
import uuid
import hashlib
import psycopg2
from typing import Optional, Dict, List, Any
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
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
    """Create user in database. Set first_name=None for invited-only users."""
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
    """Create admin user (both in user and admin tables)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        admin_id = str(uuid.uuid4())
        phone_hash = hashlib.sha256(phone.encode()).hexdigest()

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
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        phone_hash = hashlib.sha256(phone.encode()).hexdigest()

        cursor.execute('DELETE FROM admin WHERE phone = %s', (phone,))
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
    """Delete all users whose phone starts with prefix (default: +1555 for test numbers)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM admin WHERE phone LIKE %s', (f'{phone_prefix}%',))
        admin_count = cursor.rowcount

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


def get_group_by_id(group_id: str) -> Optional[Dict]:
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


def get_group_members(group_id: str) -> List[Dict[str, Any]]:
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


def get_campaign_by_id(campaign_id: str) -> Optional[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT id, title, image, type, status, end_date, duration,
                   familiar_duration, total_amount, amount_raised, description,
                   payment_details, is_deleted, total_reports, created_by,
                   created_at, updated_at
            FROM "campaign"
            WHERE id = %s
        ''', (campaign_id,))
        row = cursor.fetchone()

        if row:
            return {
                "id": row[0],
                "title": row[1],
                "image": row[2],
                "type": row[3],
                "status": row[4],
                "end_date": row[5],
                "duration": row[6],
                "familiar_duration": row[7],
                "total_amount": row[8],
                "amount_raised": row[9],
                "description": row[10],
                "payment_details": row[11],
                "is_deleted": row[12],
                "total_reports": row[13],
                "created_by": row[14],
                "created_at": row[15],
                "updated_at": row[16]
            }
        return None
    finally:
        cursor.close()
        conn.close()


def get_campaign_groups(campaign_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT cg.id, cg.group_id, g.name
            FROM campaign_group cg
            JOIN "group" g ON cg.group_id = g.id
            WHERE cg.campaign_id = %s
        ''', (campaign_id,))
        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "group_id": row[1],
                "group_name": row[2]
            }
            for row in rows
        ]
    finally:
        cursor.close()
        conn.close()


def delete_campaign_by_id(campaign_id: str) -> bool:
    """Soft delete - sets is_deleted=true"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            'UPDATE "campaign" SET is_deleted = true WHERE id = %s',
            (campaign_id,)
        )
        conn.commit()
        print(f"Deleted campaign: {campaign_id}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error deleting campaign: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def cleanup_test_campaigns(user_id: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            'UPDATE "campaign" SET is_deleted = true WHERE created_by = %s',
            (user_id,)
        )
        count = cursor.rowcount
        conn.commit()
        print(f"Cleaned up {count} campaigns for user {user_id}")
        return count
    except Exception as e:
        conn.rollback()
        print(f"Error during campaign cleanup: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()


def get_user_edge_count(campaign_id: str, user_id: str) -> int:
    """Count UserEdge entries for bug #10 deduplication testing"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT COUNT(*)
            FROM user_edge
            WHERE campaign_id = %s AND shared_to = %s
        ''', (campaign_id, user_id))

        count: int = cursor.fetchone()[0]
        return count
    finally:
        cursor.close()
        conn.close()
