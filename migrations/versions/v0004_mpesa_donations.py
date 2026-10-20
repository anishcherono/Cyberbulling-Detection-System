def upgrade():
    from extensions import database_cursor

    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Donations (
                donation_id INT AUTO_INCREMENT PRIMARY KEY,
                donor_name VARCHAR(150) NOT NULL DEFAULT 'Anonymous',
                phone_number VARCHAR(20) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                merchant_request_id VARCHAR(100) NULL,
                checkout_request_id VARCHAR(100) UNIQUE NULL,
                mpesa_receipt_number VARCHAR(50) NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
                result_code INT NULL,
                result_desc VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
        )
