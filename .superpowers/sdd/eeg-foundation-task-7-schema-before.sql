time="2026-07-17T16:39:41+07:00" level=warning msg="D:\\project\\EEG-PRE\\docker-compose.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion"
mysqldump: [Warning] Using a password on the command line interface can be insecure.

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `comics`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `comics` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `session_id` int DEFAULT NULL,
  `persona_id` int DEFAULT NULL,
  `input_story` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `generated_prompt` text COLLATE utf8mb4_unicode_ci,
  `panel_1_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `panel_2_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `panel_3_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `panel_4_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `panel_1_dialogue` text COLLATE utf8mb4_unicode_ci,
  `panel_2_dialogue` text COLLATE utf8mb4_unicode_ci,
  `panel_3_dialogue` text COLLATE utf8mb4_unicode_ci,
  `panel_4_dialogue` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `persona_id` (`persona_id`),
  KEY `ix_comics_session_id` (`session_id`),
  KEY `ix_comics_user_id` (`user_id`),
  CONSTRAINT `comics_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `comics_ibfk_2` FOREIGN KEY (`session_id`) REFERENCES `eeg_sessions` (`id`),
  CONSTRAINT `comics_ibfk_3` FOREIGN KEY (`persona_id`) REFERENCES `personas` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `eeg_features`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `eeg_features` (
  `id` int NOT NULL AUTO_INCREMENT,
  `session_id` int NOT NULL,
  `baseline_log_alpha_af7` float DEFAULT NULL,
  `baseline_log_alpha_af8` float DEFAULT NULL,
  `baseline_log_beta_af7` float DEFAULT NULL,
  `baseline_log_beta_af8` float DEFAULT NULL,
  `baseline_faa` float DEFAULT NULL COMMENT 'logAlpha(AF8)-logAlpha(AF7)',
  `baseline_arousal` float DEFAULT NULL COMMENT 'log(beta/alpha)',
  `recording_faa` float DEFAULT NULL,
  `recording_arousal` float DEFAULT NULL,
  `delta_faa` float DEFAULT NULL,
  `delta_arousal` float DEFAULT NULL,
  `epoch_size_seconds` float NOT NULL,
  `epoch_overlap_ratio` float NOT NULL,
  `feature_version` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_eeg_features_session_id` (`session_id`),
  CONSTRAINT `eeg_features_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `eeg_sessions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `eeg_sessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `eeg_sessions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `device_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `device_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `baseline_duration` int NOT NULL COMMENT 'target baseline seconds',
  `accepted_recording_duration` int NOT NULL COMMENT 'target accepted seconds',
  `wall_clock_duration` float DEFAULT NULL COMMENT 'actual elapsed seconds',
  `rejected_epoch_count` int NOT NULL,
  `pause_count` int NOT NULL,
  `raw_data_path` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('baseline','recording','completed','timeout','cancelled','failed') COLLATE utf8mb4_unicode_ci NOT NULL,
  `started_at` datetime NOT NULL DEFAULT (now()),
  `completed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_eeg_sessions_user_id` (`user_id`),
  CONSTRAINT `eeg_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `emotion_results`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `emotion_results` (
  `id` int NOT NULL AUTO_INCREMENT,
  `session_id` int NOT NULL,
  `final_emotion` enum('happy','sad','stressed','excited') COLLATE utf8mb4_unicode_ci NOT NULL,
  `rule_version` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `threshold_version` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `valence` float DEFAULT NULL,
  `arousal` float DEFAULT NULL,
  `delta_faa` float DEFAULT NULL,
  `delta_arousal` float DEFAULT NULL,
  `quality_score_avg` float DEFAULT NULL,
  `accepted_epochs` int DEFAULT NULL,
  `rejected_epochs` int DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `session_id` (`session_id`),
  CONSTRAINT `emotion_results_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `eeg_sessions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ml_training_samples`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ml_training_samples` (
  `id` int NOT NULL AUTO_INCREMENT,
  `label` enum('happy','sad','stressed','excited') COLLATE utf8mb4_unicode_ci NOT NULL,
  `focus_pct` float NOT NULL COMMENT 'beta/(alpha+beta) * 100',
  `relax_pct` float NOT NULL COMMENT 'alpha/(alpha+beta) * 100',
  `delta_faa` float DEFAULT NULL,
  `delta_arousal` float DEFAULT NULL,
  `valence` float DEFAULT NULL,
  `arousal` float DEFAULT NULL,
  `source` enum('manual_entry','user_session') COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_id` int DEFAULT NULL COMMENT 'FK to eeg_sessions if source=user_session',
  `participant_id` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Pseudonymous ID e.g. P001',
  `quality_score` float DEFAULT NULL COMMENT '0–1 signal quality',
  `valid_label` tinyint(1) NOT NULL COMMENT 'False = exclude from training',
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `session_id` (`session_id`),
  KEY `ix_ml_training_samples_label` (`label`),
  CONSTRAINT `ml_training_samples_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `eeg_sessions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `personas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `personas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `persona_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `appearance` text COLLATE utf8mb4_unicode_ci,
  `art_style` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_personas_user_id` (`user_id`),
  CONSTRAINT `personas_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ratings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ratings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `comic_id` int NOT NULL,
  `user_id` int NOT NULL,
  `stars` int NOT NULL,
  `feedback` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `ix_ratings_comic_id` (`comic_id`),
  CONSTRAINT `ratings_ibfk_1` FOREIGN KEY (`comic_id`) REFERENCES `comics` (`id`),
  CONSTRAINT `ratings_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role_id` int NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_username` (`username`),
  UNIQUE KEY `ix_users_email` (`email`),
  KEY `role_id` (`role_id`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

