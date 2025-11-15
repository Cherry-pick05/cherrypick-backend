#!/usr/bin/env python3
"""Run migration directly using root user"""
import sys
from sqlalchemy import create_engine, text

# Use root user for migration
connection_string = "mysql+pymysql://root:root@127.0.0.1:3306/cherrypick?charset=utf8mb4"

engine = create_engine(connection_string, pool_pre_ping=True)

# Migration SQL from alembic version file
migration_sql = """
-- users
ALTER TABLE `users`
  MODIFY `user_id` bigint NOT NULL AUTO_INCREMENT,
  ADD UNIQUE KEY `uq_users_device_uuid` (`device_uuid`),
  MODIFY `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- trips
ALTER TABLE `trips`
  MODIFY `trip_id` bigint NOT NULL AUTO_INCREMENT,
  ADD COLUMN `airline_code` varchar(8) NULL AFTER `country_code2`,
  ADD CONSTRAINT `fk_trips_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`),
  ADD INDEX `ix_trips_user_id` (`user_id`),
  ADD INDEX `ix_trips_country_airline` (`country_code2`, `airline_code`),
  MODIFY `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- item_images
ALTER TABLE `item_images`
  MODIFY `image_id` bigint NOT NULL AUTO_INCREMENT,
  MODIFY `s3_key` varchar(512) NOT NULL,
  ADD UNIQUE KEY `uq_item_images_s3_key` (`s3_key`),
  MODIFY `status` enum('uploaded','queued','processed','failed') NULL,
  ADD COLUMN `trip_id` bigint NULL AFTER `user_id`,
  ADD COLUMN `mime_type` varchar(64) NULL AFTER `status`,
  ADD COLUMN `width` int NULL AFTER `mime_type`,
  ADD COLUMN `height` int NULL AFTER `width`,
  ADD CONSTRAINT `fk_item_images_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`),
  ADD CONSTRAINT `fk_item_images_trip` FOREIGN KEY (`trip_id`) REFERENCES `trips`(`trip_id`),
  ADD INDEX `ix_item_images_user_created` (`user_id`, `created_at`),
  MODIFY `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP;

-- regulation_rules
ALTER TABLE `regulation_rules`
  MODIFY `rule_id` bigint NOT NULL AUTO_INCREMENT,
  MODIFY `scope` enum('country','airline') NULL,
  MODIFY `code` varchar(20) NULL,
  MODIFY `item_category` varchar(50) NULL,
  ADD UNIQUE KEY `uq_rules_scope_code_cat` (`scope`,`code`,`item_category`),
  ADD INDEX `ix_rules_scope_code` (`scope`,`code`),
  MODIFY `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- regulation_matches
ALTER TABLE `regulation_matches`
  MODIFY `id` bigint NOT NULL AUTO_INCREMENT,
  MODIFY `status` enum('allow','ban','limited') NULL,
  ADD COLUMN `user_id` bigint NULL AFTER `status`,
  ADD COLUMN `trip_id` bigint NULL AFTER `user_id`,
  ADD COLUMN `confidence` decimal(5,4) NULL AFTER `details`,
  ADD COLUMN `source` enum('detect','ocr','manual') NULL AFTER `confidence`,
  ADD COLUMN `matched_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP AFTER `created_at`,
  MODIFY `image_id` bigint NOT NULL,
  ADD CONSTRAINT `fk_matches_image` FOREIGN KEY (`image_id`) REFERENCES `item_images`(`image_id`),
  ADD CONSTRAINT `fk_matches_rule` FOREIGN KEY (`rule_id`) REFERENCES `regulation_rules`(`rule_id`),
  ADD CONSTRAINT `fk_matches_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`),
  ADD CONSTRAINT `fk_matches_trip` FOREIGN KEY (`trip_id`) REFERENCES `trips`(`trip_id`),
  ADD INDEX `ix_matches_user_trip_time` (`user_id`,`trip_id`,`matched_at`);
"""

if __name__ == "__main__":
    try:
        with engine.connect() as conn:
            # Split SQL into individual statements
            statements = [s.strip() for s in migration_sql.split(";") if s.strip()]
            for stmt in statements:
                if stmt:
                    try:
                        conn.execute(text(stmt))
                        print(f"✓ Executed: {stmt[:50]}...")
                    except Exception as e:
                        # Ignore errors for already existing constraints/indexes
                        if "Duplicate" in str(e) or "already exists" in str(e).lower():
                            print(f"⚠ Skipped (already exists): {stmt[:50]}...")
                        else:
                            print(f"✗ Error: {e}")
                            print(f"  Statement: {stmt[:100]}...")
            conn.commit()
            print("\n✅ Migration completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

