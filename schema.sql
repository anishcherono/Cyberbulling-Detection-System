-- ============================================================
-- Nish Institution Cyberbullying Detection System
-- Complete MySQL Database Schema
-- Database: Cyberbulling_system
-- ============================================================

CREATE DATABASE IF NOT EXISTS Cyberbulling_system 
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE Cyberbulling_system;

SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- Table structure for alerts
-- ------------------------------------------------------------
CREATE TABLE `alerts` (
  `alert_id` int NOT NULL AUTO_INCREMENT,
  `message_id` int NOT NULL,
  `alert_type` varchar(50) NOT NULL,
  `alert_message` text NOT NULL,
  `status` varchar(30) NOT NULL DEFAULT 'unread',
  `date_created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`alert_id`),
  KEY `message_id` (`message_id`),
  CONSTRAINT `alerts_ibfk_1` FOREIGN KEY (`message_id`) REFERENCES `messages` (`message_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- Table structure for announcements
-- ------------------------------------------------------------
CREATE TABLE `announcements` (
  `announcement_id` int NOT NULL AUTO_INCREMENT,
  `teacher_id` int NOT NULL,
  `title` varchar(150) NOT NULL,
  `content` text NOT NULL,
  `detection_result` varchar(100) NOT NULL,
  `confidence` decimal(6,5) NOT NULL DEFAULT '0.00000',
  `status` varchar(30) NOT NULL DEFAULT 'published',
  `date_created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`announcement_id`),
  KEY `teacher_id` (`teacher_id`),
  CONSTRAINT `announcements_ibfk_1` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- Table structure for discussionreplies
-- ------------------------------------------------------------
CREATE TABLE `discussionreplies` (
  `reply_id` int NOT NULL AUTO_INCREMENT,
  `message_id` int DEFAULT NULL,
  `announcement_id` int DEFAULT NULL,
  `author_id` int NOT NULL,
  `reply_text` text NOT NULL,
  `detection_result` varchar(100) NOT NULL,
  `confidence` decimal(6,5) NOT NULL DEFAULT '0.00000',
  `status` varchar(30) NOT NULL DEFAULT 'checked',
  `date_created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`reply_id`),
  KEY `message_id` (`message_id`),
  KEY `announcement_id` (`announcement_id`),
  KEY `author_id` (`author_id`),
  CONSTRAINT `discussionreplies_ibfk_1` FOREIGN KEY (`message_id`) REFERENCES `messages` (`message_id`) ON DELETE CASCADE,
  CONSTRAINT `discussionreplies_ibfk_2` FOREIGN KEY (`announcement_id`) REFERENCES `announcements` (`announcement_id`) ON DELETE CASCADE,
  CONSTRAINT `discussionreplies_ibfk_3` FOREIGN KEY (`author_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- Table structure for donations
-- ------------------------------------------------------------
CREATE TABLE `donations` (
  `donation_id` int NOT NULL AUTO_INCREMENT,
  `donor_name` varchar(150) NOT NULL DEFAULT 'Anonymous',
  `phone_number` varchar(20) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `merchant_request_id` varchar(100) DEFAULT NULL,
  `checkout_request_id` varchar(100) DEFAULT NULL,
  `mpesa_receipt_number` varchar(50) DEFAULT NULL,
  `status` varchar(30) NOT NULL DEFAULT 'PENDING',
  `result_code` int DEFAULT NULL,
  `result_desc` varchar(255) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`donation_id`),
  KEY `idx_donations_status` (`status`),
  KEY `idx_donations_checkout` (`checkout_request_id`),
  KEY `idx_donations_merchant` (`merchant_request_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- Table structure for messageinboxdeletions
-- ------------------------------------------------------------
CREATE TABLE `messageinboxdeletions` (
  `user_id` int NOT NULL,
  `message_id` int NOT NULL,
  `date_deleted` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`message_id`),
  KEY `message_id` (`message_id`),
  CONSTRAINT `messageinboxdeletions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `messageinboxdeletions_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `messages` (`message_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- Table structure for messages
-- ------------------------------------------------------------
CREATE TABLE `messages` (
  `message_id` int NOT NULL AUTO_INCREMENT,
  `sender_id` int NOT NULL,
  `recipient_id` int DEFAULT NULL,
  `message_text` text NOT NULL,
  `detection_result` varchar(100) NOT NULL,
  `confidence` decimal(6,5) NOT NULL DEFAULT '0.00000',
  `status` varchar(30) NOT NULL DEFAULT 'checked',
  `date_sent` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`message_id`),
  KEY `sender_id` (`sender_id`),
  KEY `recipient_id` (`recipient_id`),
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`sender_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `messages_ibfk_2` FOREIGN KEY (`recipient_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- Table structure for notifications
-- ------------------------------------------------------------
CREATE TABLE `notifications` (
  `notification_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `notification_type` varchar(50) NOT NULL,
  `notification_message` text NOT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT '0',
  `date_created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`notification_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- Table structure for reports
-- ------------------------------------------------------------
CREATE TABLE `reports` (
  `report_id` int NOT NULL AUTO_INCREMENT,
  `message_id` int DEFAULT NULL,
  `announcement_id` int DEFAULT NULL,
  `reply_id` int DEFAULT NULL,
  `reported_by` int NOT NULL,
  `reason` text NOT NULL,
  `action_taken` varchar(100) NOT NULL DEFAULT 'Pending',
  `status` varchar(30) NOT NULL DEFAULT 'Pending',
  `date_reported` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`report_id`),
  KEY `message_id` (`message_id`),
  KEY `announcement_id` (`announcement_id`),
  KEY `reply_id` (`reply_id`),
  KEY `reported_by` (`reported_by`),
  CONSTRAINT `reports_ibfk_1` FOREIGN KEY (`message_id`) REFERENCES `messages` (`message_id`) ON DELETE SET NULL,
  CONSTRAINT `reports_ibfk_2` FOREIGN KEY (`announcement_id`) REFERENCES `announcements` (`announcement_id`) ON DELETE CASCADE,
  CONSTRAINT `reports_ibfk_3` FOREIGN KEY (`reply_id`) REFERENCES `discussionreplies` (`reply_id`) ON DELETE CASCADE,
  CONSTRAINT `reports_ibfk_4` FOREIGN KEY (`reported_by`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- Table structure for users
-- ------------------------------------------------------------
CREATE TABLE `users` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `full_name` varchar(200) NOT NULL,
  `institution_id` varchar(100) DEFAULT NULL,
  `email` varchar(255) NOT NULL,
  `username` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` varchar(50) NOT NULL,
  `status` varchar(30) NOT NULL DEFAULT 'active',
  `date_created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS = 1;
