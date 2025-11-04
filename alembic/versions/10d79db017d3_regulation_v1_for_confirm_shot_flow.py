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
    op.execute("""
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
    """)


def downgrade() -> None:
    """Downgrade schema."""
    pass
