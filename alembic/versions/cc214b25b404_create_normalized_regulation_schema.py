"""create normalized regulation schema

Revision ID: cc214b25b404
Revises: 10d79db017d3
Create Date: 2025-11-11 14:11:41.175799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc214b25b404'
down_revision: Union[str, Sequence[str], None] = '10d79db017d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create rule_sets table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'rule_sets'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `rule_sets` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `scope` enum('international','country','airline') NOT NULL,
                `code` varchar(64) NOT NULL,
                `name` varchar(255) NOT NULL,
                `source_url` text,
                `source_etag` varchar(255),
                `imported_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_ruleset_scope_code` (`scope`, `code`)
            )
        """)

    # Create item_rules table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_rules'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `item_rules` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `rule_set_id` bigint NOT NULL,
                `item_name` varchar(255),
                `item_category` varchar(64) NOT NULL,
                `severity` enum('info','warn','block') NOT NULL,
                `notes` text,
                PRIMARY KEY (`id`),
                KEY `idx_itemrule_category` (`item_category`),
                CONSTRAINT `fk_itemrule_ruleset` FOREIGN KEY (`rule_set_id`) REFERENCES `rule_sets`(`id`) ON DELETE CASCADE
            )
        """)

    # Create applicability table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'applicability'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `applicability` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `item_rule_id` bigint NOT NULL,
                `route_type` enum('domestic','international'),
                `region` varchar(64),
                `cabin_class` varchar(32),
                `fare_class` varchar(32),
                `passenger_type` varchar(32),
                `effective_from` date,
                `effective_until` date,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_app_scope` (`item_rule_id`, `route_type`, `region`, `cabin_class`, `fare_class`, `passenger_type`, `effective_from`, `effective_until`),
                KEY `idx_app_region` (`region`),
                KEY `idx_app_cabin` (`cabin_class`),
                KEY `idx_app_fare` (`fare_class`),
                CONSTRAINT `fk_app_itemrule` FOREIGN KEY (`item_rule_id`) REFERENCES `item_rules`(`id`) ON DELETE CASCADE
            )
        """)

    # Create constraints_quant table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'constraints_quant'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `constraints_quant` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `applicability_id` bigint NOT NULL,
                `max_weight_kg` decimal(6,2),
                `per_piece_max_weight_kg` decimal(6,2),
                `max_pieces` smallint,
                `max_total_cm` smallint,
                `size_length_cm` smallint,
                `size_width_cm` smallint,
                `size_height_cm` smallint,
                `max_container_ml` smallint,
                `max_total_bag_l` decimal(5,2),
                `lithium_ion_max_wh` smallint,
                `lithium_metal_g` decimal(6,2),
                `max_weight_per_person_kg` decimal(6,2),
                `operator_approval_required` tinyint(1),
                `carry_on_allowed` tinyint(1),
                `checked_allowed` tinyint(1),
                `on_person_allowed` tinyint(1),
                `ext` json,
                PRIMARY KEY (`id`),
                KEY `idx_constr_allow` (`carry_on_allowed`, `checked_allowed`),
                KEY `idx_constr_pieces` (`max_pieces`),
                KEY `idx_constr_size` (`max_total_cm`, `size_length_cm`, `size_width_cm`, `size_height_cm`),
                KEY `idx_constr_battery` (`lithium_ion_max_wh`, `lithium_metal_g`),
                KEY `idx_constr_liquid` (`max_container_ml`, `max_total_bag_l`),
                CONSTRAINT `fk_constr_app` FOREIGN KEY (`applicability_id`) REFERENCES `applicability`(`id`) ON DELETE CASCADE
            )
        """)

    # Create constraint_extras table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'constraint_extras'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `constraint_extras` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `constraints_id` bigint NOT NULL,
                `extra_type` enum('additional_item','allowed_item','exception') NOT NULL,
                `label` varchar(64) NOT NULL,
                `details` json,
                PRIMARY KEY (`id`),
                KEY `idx_extra_type` (`extra_type`, `label`),
                CONSTRAINT `fk_extra_constr` FOREIGN KEY (`constraints_id`) REFERENCES `constraints_quant`(`id`) ON DELETE CASCADE
            )
        """)

    # Create taxonomy table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'taxonomy'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `taxonomy` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `canonical_key` varchar(128) NOT NULL,
                `category` varchar(64) NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_taxo_key` (`canonical_key`),
                KEY `idx_taxo_cat` (`category`)
            )
        """)

    # Create taxonomy_synonym table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'taxonomy_synonym'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `taxonomy_synonym` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `taxonomy_id` bigint NOT NULL,
                `synonym` varchar(128) NOT NULL,
                `lang` varchar(8),
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_synonym` (`synonym`, `lang`),
                KEY `idx_synonym` (`synonym`),
                CONSTRAINT `fk_syn_taxo` FOREIGN KEY (`taxonomy_id`) REFERENCES `taxonomy`(`id`) ON DELETE CASCADE
            )
        """)

    # Create precedence_policy table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'precedence_policy'
    """))
    if result.fetchone()[0] == 0:
        op.execute("""
            CREATE TABLE `precedence_policy` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `name` varchar(128) NOT NULL,
                `policy_json` json NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_policy_name` (`name`)
            )
        """)

    # Modify regulation_matches table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'rule_id'
    """))
    if result.fetchone()[0] > 0:
        # Drop foreign key constraint first
        result = conn.execute(sa.text("""
            SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
            WHERE table_schema = DATABASE() 
            AND table_name = 'regulation_matches' 
            AND constraint_name = 'fk_matches_rule'
        """))
        if result.fetchone()[0] > 0:
            op.execute("ALTER TABLE `regulation_matches` DROP FOREIGN KEY `fk_matches_rule`")
        
        op.execute("ALTER TABLE `regulation_matches` DROP COLUMN `rule_id`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'item_rule_id'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD COLUMN `item_rule_id` bigint NULL AFTER `image_id`")
        
        result = conn.execute(sa.text("""
            SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
            WHERE table_schema = DATABASE() 
            AND table_name = 'regulation_matches' 
            AND constraint_name = 'fk_regulation_matches_item_rule'
        """))
        if result.fetchone()[0] == 0:
            op.execute("ALTER TABLE `regulation_matches` ADD CONSTRAINT `fk_regulation_matches_item_rule` FOREIGN KEY (`item_rule_id`) REFERENCES `item_rules`(`id`) ON DELETE SET NULL")


def downgrade() -> None:
    conn = op.get_bind()

    # Revert regulation_matches table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'item_rule_id'
    """))
    if result.fetchone()[0] > 0:
        result = conn.execute(sa.text("""
            SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
            WHERE table_schema = DATABASE() 
            AND table_name = 'regulation_matches' 
            AND constraint_name = 'fk_regulation_matches_item_rule'
        """))
        if result.fetchone()[0] > 0:
            op.execute("ALTER TABLE `regulation_matches` DROP FOREIGN KEY `fk_regulation_matches_item_rule`")
        
        op.execute("ALTER TABLE `regulation_matches` DROP COLUMN `item_rule_id`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'regulation_matches' 
        AND column_name = 'rule_id'
    """))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE `regulation_matches` ADD COLUMN `rule_id` bigint NOT NULL AFTER `image_id`")
        
        result = conn.execute(sa.text("""
            SELECT COUNT(*) as cnt FROM information_schema.table_constraints 
            WHERE table_schema = DATABASE() 
            AND table_name = 'regulation_matches' 
            AND constraint_name = 'fk_matches_rule'
        """))
        if result.fetchone()[0] == 0:
            op.execute("ALTER TABLE `regulation_matches` ADD CONSTRAINT `fk_matches_rule` FOREIGN KEY (`rule_id`) REFERENCES `regulation_rules`(`rule_id`) ON DELETE SET NULL")

    # Drop tables in reverse order
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'precedence_policy'
    """))
    if result.fetchone()[0] > 0:
        op.execute("DROP TABLE IF EXISTS `precedence_policy`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'taxonomy_synonym'
    """))
    if result.fetchone()[0] > 0:
        op.execute("DROP TABLE IF EXISTS `taxonomy_synonym`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'taxonomy'
    """))
    if result.fetchone()[0] > 0:
        op.execute("DROP TABLE IF EXISTS `taxonomy`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'constraint_extras'
    """))
    if result.fetchone()[0] > 0:
        op.execute("DROP TABLE IF EXISTS `constraint_extras`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'constraints_quant'
    """))
    if result.fetchone()[0] > 0:
        op.execute("DROP TABLE IF EXISTS `constraints_quant`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'applicability'
    """))
    if result.fetchone()[0] > 0:
        op.execute("DROP TABLE IF EXISTS `applicability`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'item_rules'
    """))
    if result.fetchone()[0] > 0:
        op.execute("DROP TABLE IF EXISTS `item_rules`")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'rule_sets'
    """))
    if result.fetchone()[0] > 0:
        op.execute("DROP TABLE IF EXISTS `rule_sets`")
