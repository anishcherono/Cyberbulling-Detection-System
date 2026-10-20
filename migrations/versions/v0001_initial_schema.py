def upgrade():
    from extensions import database_cursor

    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(200) NOT NULL,
                institution_id VARCHAR(100) NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                username VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Messages (
                message_id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                recipient_id INT NULL,
                message_text TEXT NOT NULL,
                detection_result VARCHAR(100) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'checked',
                date_sent TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_message_sender
                    FOREIGN KEY (sender_id) REFERENCES Users(user_id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_message_recipient
                    FOREIGN KEY (recipient_id) REFERENCES Users(user_id)
                    ON DELETE SET NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Announcements (
                announcement_id INT AUTO_INCREMENT PRIMARY KEY,
                teacher_id INT NOT NULL,
                title VARCHAR(150) NOT NULL,
                content TEXT NOT NULL,
                detection_result VARCHAR(100) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'published',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_announcement_teacher
                    FOREIGN KEY (teacher_id) REFERENCES Users(user_id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS DiscussionReplies (
                reply_id INT AUTO_INCREMENT PRIMARY KEY,
                message_id INT NULL,
                announcement_id INT NULL,
                author_id INT NOT NULL,
                reply_text TEXT NOT NULL,
                detection_result VARCHAR(100) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'checked',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_reply_message
                    FOREIGN KEY (message_id) REFERENCES Messages(message_id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_reply_announcement
                    FOREIGN KEY (announcement_id)
                    REFERENCES Announcements(announcement_id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_reply_author
                    FOREIGN KEY (author_id) REFERENCES Users(user_id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Alerts (
                alert_id INT AUTO_INCREMENT PRIMARY KEY,
                message_id INT NOT NULL,
                alert_type VARCHAR(50) NOT NULL,
                alert_message TEXT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'unread',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_alert_message
                    FOREIGN KEY (message_id) REFERENCES Messages(message_id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Reports (
                report_id INT AUTO_INCREMENT PRIMARY KEY,
                message_id INT NULL,
                announcement_id INT NULL,
                reply_id INT NULL,
                reported_by INT NOT NULL,
                reason TEXT NOT NULL,
                action_taken VARCHAR(100) NOT NULL DEFAULT 'Pending',
                status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                date_reported TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_report_message
                    FOREIGN KEY (message_id) REFERENCES Messages(message_id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_report_announcement
                    FOREIGN KEY (announcement_id)
                    REFERENCES Announcements(announcement_id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_report_by
                    FOREIGN KEY (reported_by) REFERENCES Users(user_id)
                    ON DELETE CASCADE
            )
            """
        )
