def upgrade():
    from extensions import database_cursor

    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'Users'
              AND COLUMN_NAME = 'status'
            """
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                ALTER TABLE Users
                ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'active'
                AFTER role
                """
            )
