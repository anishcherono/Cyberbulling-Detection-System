def _column_exists(cursor, table, column):
    cursor.execute(
        """
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table, column),
    )
    return cursor.fetchone()[0] > 0


def _foreign_key_exists(cursor, table, column, referenced_table):
    cursor.execute(
        """
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
          AND REFERENCED_TABLE_NAME = %s
        """,
        (table, column, referenced_table),
    )
    return cursor.fetchone()[0] > 0


def upgrade():
    from extensions import database_cursor

    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS MessageInboxDeletions (
                user_id INT NOT NULL,
                message_id INT NOT NULL,
                date_deleted TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, message_id),
                CONSTRAINT fk_inbox_deletion_user
                    FOREIGN KEY (user_id) REFERENCES Users(user_id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_inbox_deletion_message
                    FOREIGN KEY (message_id) REFERENCES Messages(message_id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Notifications (
                notification_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                notification_message TEXT NOT NULL,
                is_read BOOLEAN NOT NULL DEFAULT FALSE,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_notification_user
                    FOREIGN KEY (user_id) REFERENCES Users(user_id)
                    ON DELETE CASCADE
            )
            """
        )

        if not _column_exists(cursor, "Messages", "recipient_id"):
            cursor.execute(
                "ALTER TABLE Messages ADD COLUMN recipient_id INT NULL AFTER sender_id"
            )
        if not _foreign_key_exists(cursor, "Messages", "recipient_id", "Users"):
            cursor.execute(
                """
                ALTER TABLE Messages
                ADD CONSTRAINT fk_message_recipient
                FOREIGN KEY (recipient_id) REFERENCES Users(user_id)
                ON DELETE SET NULL
                """
            )

        cursor.execute(
            """
            SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'Reports'
              AND COLUMN_NAME = 'message_id'
            """
        )
        message_id_column = cursor.fetchone()
        if message_id_column and message_id_column[0] == "NO":
            cursor.execute("ALTER TABLE Reports MODIFY message_id INT NULL")

        for column in ("announcement_id", "reply_id"):
            if not _column_exists(cursor, "Reports", column):
                cursor.execute(f"ALTER TABLE Reports ADD COLUMN {column} INT NULL")

        for column, target in (
            ("announcement_id", "Announcements"),
            ("reply_id", "DiscussionReplies"),
        ):
            if not _foreign_key_exists(cursor, "Reports", column, target):
                constraint = f"fk_report_{column}"
                cursor.execute(
                    f"""
                    ALTER TABLE Reports
                    ADD CONSTRAINT {constraint}
                    FOREIGN KEY ({column}) REFERENCES {target}({column})
                    ON DELETE SET NULL
                    """
                )
