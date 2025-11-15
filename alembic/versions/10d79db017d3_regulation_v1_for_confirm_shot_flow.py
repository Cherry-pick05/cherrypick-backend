"""regulation v1 for confirm-shot flow

Revision ID: 10d79db017d3
Revises: 
Create Date: 2025-10-28 21:37:35.239195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10d79db017d3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    conn = op.get_bind()
    
    # Check if tables exist, create them if they don't
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'users'
    """))
    if result.fetchone()[0] == 0:
        # Create users table
        op.execute("""
            CREATE TABLE `users` (
                `user_id` bigint NOT NULL AUTO_INCREMENT,
                `device_uuid` varchar(36),
                `name` varchar(100),
                `locale` varchar(10),
                `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`user_id`)
            )
        """)
    
    # users table modifications
    op.execute("""
        ALTER TABLE `users`
          MODIFY `user_id` bigint NOT NULL AUTO_INCREMENT,
          MODIFY `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
          MODIFY `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    """)
    
    # Check if unique key exists before adding
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'users' 
        AND constraint_name = 'uq_users_device_uuid'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `users` ADD UNIQUE KEY `uq_users_device_uuid` (`device_uuid`)")

    # Check if trips table exists
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trips'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `trips` (
                `trip_id` bigint NOT NULL AUTO_INCREMENT,
                `city` varchar(80),
                `start_date` date,
                `end_date` date,
                `country_code2` varchar(2) NOT NULL,
                `airline_code` varchar(8),
                `user_id` bigint NOT NULL,
                `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`trip_id`)
            )
        """)
    
    # trips table modifications
    op.execute("""
        ALTER TABLE `trips`
          MODIFY `trip_id` bigint NOT NULL AUTO_INCREMENT,
          MODIFY `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
          MODIFY `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    """)
    
    # Check if column exists before adding
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trips' 
        AND column_name = 'airline_code'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `trips` ADD COLUMN `airline_code` varchar(8) NULL AFTER `country_code2`")
    
    # Add constraints and indexes
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trips' 
        AND constraint_name = 'fk_trips_user'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `trips` ADD CONSTRAINT `fk_trips_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.statistics 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trips' 
        AND index_name = 'ix_trips_user_id'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `trips` ADD INDEX `ix_trips_user_id` (`user_id`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.statistics 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trips' 
        AND index_name = 'ix_trips_country_airline'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `trips` ADD INDEX `ix_trips_country_airline` (`country_code2`, `airline_code`)")

    # Check if item_images table exists
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `item_images` (
                `image_id` bigint NOT NULL AUTO_INCREMENT,
                `s3_key` varchar(512) NOT NULL,
                `status` enum('uploaded','queued','processed','failed'),
                `mime_type` varchar(64),
                `width` int,
                `height` int,
                `rekognition_labels` json,
                `user_id` bigint NOT NULL,
                `trip_id` bigint,
                `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`image_id`)
            )
        """)
    
    # item_images table modifications
    op.execute("""
        ALTER TABLE `item_images`
          MODIFY `image_id` bigint NOT NULL AUTO_INCREMENT,
          MODIFY `s3_key` varchar(512) NOT NULL,
          MODIFY `status` enum('uploaded','queued','processed','failed') NULL,
          MODIFY `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP
    """)
    
    # Check and add columns
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images' 
        AND column_name = 'trip_id'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `item_images` ADD COLUMN `trip_id` bigint NULL AFTER `user_id`")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images' 
        AND column_name = 'mime_type'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `item_images` ADD COLUMN `mime_type` varchar(64) NULL AFTER `status`")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images' 
        AND column_name = 'width'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `item_images` ADD COLUMN `width` int NULL AFTER `mime_type`")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images' 
        AND column_name = 'height'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `item_images` ADD COLUMN `height` int NULL AFTER `width`")
    
    # Add constraints and indexes for item_images
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images' 
        AND constraint_name = 'uq_item_images_s3_key'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `item_images` ADD UNIQUE KEY `uq_item_images_s3_key` (`s3_key`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images' 
        AND constraint_name = 'fk_item_images_user'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `item_images` ADD CONSTRAINT `fk_item_images_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images' 
        AND constraint_name = 'fk_item_images_trip'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `item_images` ADD CONSTRAINT `fk_item_images_trip` FOREIGN KEY (`trip_id`) REFERENCES `trips`(`trip_id`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.statistics 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_images' 
        AND index_name = 'ix_item_images_user_created'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `item_images` ADD INDEX `ix_item_images_user_created` (`user_id`, `created_at`)")

    # Check if regulation_rules table exists
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_rules'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `regulation_rules` (
                `rule_id` bigint NOT NULL AUTO_INCREMENT,
                `scope` enum('country','airline'),
                `code` varchar(20),
                `item_category` varchar(50),
                `constraints` json,
                `severity` enum('info','warn','block'),
                `notes` text,
                `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`rule_id`)
            )
        """)
    
    # regulation_rules table modifications
    op.execute("""
        ALTER TABLE `regulation_rules`
          MODIFY `rule_id` bigint NOT NULL AUTO_INCREMENT,
          MODIFY `scope` enum('country','airline') NULL,
          MODIFY `code` varchar(20) NULL,
          MODIFY `item_category` varchar(50) NULL,
          MODIFY `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
          MODIFY `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    """)
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_rules' 
        AND constraint_name = 'uq_rules_scope_code_cat'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_rules` ADD UNIQUE KEY `uq_rules_scope_code_cat` (`scope`,`code`,`item_category`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.statistics 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_rules' 
        AND index_name = 'ix_rules_scope_code'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_rules` ADD INDEX `ix_rules_scope_code` (`scope`,`code`)")

    # Check if regulation_matches table exists
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `regulation_matches` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `status` enum('allow','ban','limited'),
                `user_id` bigint,
                `trip_id` bigint,
                `image_id` bigint NOT NULL,
                `rule_id` bigint NOT NULL,
                `details` json,
                `confidence` decimal(5,4),
                `source` enum('detect','ocr','manual'),
                `created_at` timestamp,
                `matched_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`)
            )
        """)
    
    # regulation_matches table modifications
    op.execute("""
        ALTER TABLE `regulation_matches`
          MODIFY `id` bigint NOT NULL AUTO_INCREMENT,
          MODIFY `status` enum('allow','ban','limited') NULL,
          MODIFY `image_id` bigint NOT NULL
    """)
    
    # Check and add columns
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'user_id'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD COLUMN `user_id` bigint NULL AFTER `status`")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'trip_id'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD COLUMN `trip_id` bigint NULL AFTER `user_id`")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'confidence'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD COLUMN `confidence` decimal(5,4) NULL AFTER `details`")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'source'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD COLUMN `source` enum('detect','ocr','manual') NULL AFTER `confidence`")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'matched_at'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD COLUMN `matched_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP AFTER `created_at`")
    
    # Add constraints and indexes for regulation_matches
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND constraint_name = 'fk_matches_image'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD CONSTRAINT `fk_matches_image` FOREIGN KEY (`image_id`) REFERENCES `item_images`(`image_id`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND constraint_name = 'fk_matches_rule'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD CONSTRAINT `fk_matches_rule` FOREIGN KEY (`rule_id`) REFERENCES `regulation_rules`(`rule_id`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND constraint_name = 'fk_matches_user'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD CONSTRAINT `fk_matches_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND constraint_name = 'fk_matches_trip'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD CONSTRAINT `fk_matches_trip` FOREIGN KEY (`trip_id`) REFERENCES `trips`(`trip_id`)")
    
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.statistics 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND index_name = 'ix_matches_user_trip_time'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD INDEX `ix_matches_user_trip_time` (`user_id`,`trip_id`,`matched_at`)")


def downgrade() -> None:
    """Downgrade schema."""
    pass
