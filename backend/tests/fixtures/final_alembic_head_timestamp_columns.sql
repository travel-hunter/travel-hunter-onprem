BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_create_v0_3_schema

CREATE TABLE users (
    id BIGSERIAL NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    nickname VARCHAR(50) NOT NULL,
    birth_date DATE,
    gender VARCHAR(10),
    region VARCHAR(50),
    preferred_regions VARCHAR(255),
    residence_area VARCHAR(50),
    onboarding_completed BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (email)
);

CREATE TABLE policies (
    id BIGSERIAL NOT NULL,
    slug VARCHAR(160),
    title VARCHAR(200) NOT NULL,
    organization VARCHAR(100),
    policy_type VARCHAR(30),
    description TEXT,
    benefit_amount INTEGER,
    benefit_detail TEXT,
    target_condition TEXT,
    region VARCHAR(50) NOT NULL,
    start_date DATE,
    end_date DATE,
    official_url VARCHAR(500),
    policy_comment VARCHAR(300),
    policy_period VARCHAR(100),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (slug)
);

CREATE INDEX idx_policies_slug ON policies (slug);

CREATE TABLE auth_refresh_tokens (
    id BIGSERIAL NOT NULL,
    user_id BIGINT NOT NULL,
    refresh_token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX idx_auth_refresh_tokens_user_id ON auth_refresh_tokens (user_id);

CREATE TABLE social_accounts (
    id BIGSERIAL NOT NULL,
    user_id BIGINT NOT NULL,
    provider VARCHAR(20) NOT NULL,
    provider_id VARCHAR(100) NOT NULL,
    provider_nickname VARCHAR(100),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (provider, provider_id)
);

CREATE TABLE policy_documents (
    id BIGSERIAL NOT NULL,
    policy_id BIGINT NOT NULL,
    document_name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    is_required BOOLEAN DEFAULT true NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(policy_id) REFERENCES policies (id) ON DELETE CASCADE
);

CREATE TABLE trips (
    id BIGSERIAL NOT NULL,
    owner_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    region VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE TABLE trip_days (
    id BIGSERIAL NOT NULL,
    trip_id BIGINT NOT NULL,
    day_number INTEGER NOT NULL,
    date DATE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    UNIQUE (trip_id, date),
    UNIQUE (trip_id, day_number)
);

CREATE TABLE trip_places (
    id BIGSERIAL NOT NULL,
    trip_day_id BIGINT NOT NULL,
    place_name VARCHAR(200) NOT NULL,
    address VARCHAR(500),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    visit_time TIME WITHOUT TIME ZONE,
    order_num INTEGER,
    memo TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(trip_day_id) REFERENCES trip_days (id) ON DELETE CASCADE
);

CREATE TABLE trip_members (
    id BIGSERIAL NOT NULL,
    trip_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    role VARCHAR(20) DEFAULT 'editor' NOT NULL,
    joined_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id),
    UNIQUE (trip_id, user_id)
);

CREATE TABLE trip_policies (
    id BIGSERIAL NOT NULL,
    trip_id BIGINT NOT NULL,
    policy_id BIGINT NOT NULL,
    added_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(policy_id) REFERENCES policies (id),
    FOREIGN KEY(trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    UNIQUE (trip_id, policy_id)
);

CREATE TABLE trip_invites (
    id BIGSERIAL NOT NULL,
    trip_id BIGINT NOT NULL,
    invite_token VARCHAR(100) NOT NULL,
    created_by BIGINT NOT NULL,
    accepted_at TIMESTAMP WITHOUT TIME ZONE,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(created_by) REFERENCES users (id),
    FOREIGN KEY(trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    UNIQUE (invite_token)
);

CREATE INDEX idx_trip_invites_token ON trip_invites (invite_token);

CREATE INDEX idx_trip_invites_trip_id ON trip_invites (trip_id);

CREATE TABLE recommendations (
    id BIGSERIAL NOT NULL,
    user_id BIGINT NOT NULL,
    trip_id BIGINT,
    query TEXT,
    result JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(trip_id) REFERENCES trips (id),
    FOREIGN KEY(user_id) REFERENCES users (id)
);

INSERT INTO alembic_version (version_num) VALUES ('0001_create_v0_3_schema') RETURNING alembic_version.version_num;

-- Running upgrade 0001_create_v0_3_schema -> 0002_user_profile_prefs

ALTER TABLE users ADD COLUMN travel_style VARCHAR(50);

ALTER TABLE users ADD COLUMN travel_budget VARCHAR(50);

UPDATE alembic_version SET version_num='0002_user_profile_prefs' WHERE alembic_version.version_num = '0001_create_v0_3_schema';

-- Running upgrade 0002_user_profile_prefs -> 0003_user_saved_policies

CREATE TABLE user_saved_policies (
    id BIGSERIAL NOT NULL,
    user_id BIGINT NOT NULL,
    policy_id BIGINT NOT NULL,
    saved_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(policy_id) REFERENCES policies (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (user_id, policy_id)
);

CREATE INDEX ix_user_saved_policies_policy_id ON user_saved_policies (policy_id);

CREATE INDEX ix_user_saved_policies_user_id ON user_saved_policies (user_id);

UPDATE alembic_version SET version_num='0003_user_saved_policies' WHERE alembic_version.version_num = '0002_user_profile_prefs';

-- Running upgrade 0003_user_saved_policies -> 0004_policy_apply_url

ALTER TABLE policies ADD COLUMN apply_url VARCHAR(500);

UPDATE alembic_version SET version_num='0004_policy_apply_url' WHERE alembic_version.version_num = '0003_user_saved_policies';

-- Running upgrade 0004_policy_apply_url -> 0005_add_trip_invite_role

ALTER TABLE trip_invites ADD COLUMN role VARCHAR(20) DEFAULT 'editor' NOT NULL;

UPDATE alembic_version SET version_num='0005_add_trip_invite_role' WHERE alembic_version.version_num = '0004_policy_apply_url';

-- Running upgrade 0005_add_trip_invite_role -> 0006_user_notification_settings

CREATE TABLE user_notification_settings (
    id BIGSERIAL NOT NULL,
    user_id BIGINT NOT NULL,
    deadline_enabled BOOLEAN DEFAULT 'true' NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (user_id)
);

UPDATE alembic_version SET version_num='0006_user_notification_settings' WHERE alembic_version.version_num = '0005_add_trip_invite_role';

-- Running upgrade 0006_user_notification_settings -> 0007_notification_delivery

ALTER TABLE users ADD COLUMN phone_number VARCHAR(30);

ALTER TABLE users ADD COLUMN phone_verified_at TIMESTAMP WITHOUT TIME ZONE;

CREATE TABLE notification_deliveries (
    id BIGSERIAL NOT NULL,
    user_id BIGINT NOT NULL,
    policy_id BIGINT NOT NULL,
    channel VARCHAR(30) NOT NULL,
    lead_day INTEGER NOT NULL,
    target_deadline_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    attempt_count INTEGER DEFAULT '0' NOT NULL,
    provider_message_id VARCHAR(100),
    error_message TEXT,
    scheduled_at TIMESTAMP WITHOUT TIME ZONE,
    sent_at TIMESTAMP WITHOUT TIME ZONE,
    failed_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(policy_id) REFERENCES policies (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (user_id, policy_id, channel, lead_day, target_deadline_date)
);

CREATE INDEX ix_notification_deliveries_policy_id ON notification_deliveries (policy_id);

CREATE INDEX ix_notification_deliveries_user_id ON notification_deliveries (user_id);

UPDATE alembic_version SET version_num='0007_notification_delivery' WHERE alembic_version.version_num = '0006_user_notification_settings';

-- Running upgrade 0007_notification_delivery -> 0008_password_reset_tokens

CREATE TABLE password_reset_tokens (
    id BIGSERIAL NOT NULL,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    used_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
);

CREATE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

UPDATE alembic_version SET version_num='0008_password_reset_tokens' WHERE alembic_version.version_num = '0007_notification_delivery';

-- Running upgrade 0008_password_reset_tokens -> 0009_add_trip_status

ALTER TABLE trips ADD COLUMN status VARCHAR(20) DEFAULT 'draft';

UPDATE trips SET status = 'confirmed' WHERE status IS NULL OR status = 'draft';

ALTER TABLE trips ALTER COLUMN status SET NOT NULL;

UPDATE alembic_version SET version_num='0009_add_trip_status' WHERE alembic_version.version_num = '0008_password_reset_tokens';

-- Running upgrade 0009_add_trip_status -> 0010_external_source_records

CREATE TABLE external_source_records (
    id BIGSERIAL NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    source_category VARCHAR(80) NOT NULL,
    external_id VARCHAR(160) NOT NULL,
    canonical_key VARCHAR(160) NOT NULL,
    detail_url VARCHAR(500),
    collected_page_url VARCHAR(500) NOT NULL,
    title VARCHAR(300) NOT NULL,
    organizer_text VARCHAR(300) NOT NULL,
    organizers JSONB NOT NULL,
    region VARCHAR(50),
    city VARCHAR(80),
    is_nationwide BOOLEAN DEFAULT 'false' NOT NULL,
    status_text VARCHAR(50),
    status VARCHAR(30) NOT NULL,
    start_date DATE,
    end_date DATE,
    benefit_text TEXT NOT NULL,
    benefit_value_text VARCHAR(300),
    extracted_amount_krw INTEGER,
    extracted_discount_percent INTEGER,
    benefit_value_type VARCHAR(30) NOT NULL,
    tags JSONB NOT NULL,
    contact_text VARCHAR(200),
    inferred_travel_styles JSONB NOT NULL,
    confidence INTEGER NOT NULL,
    field_completeness INTEGER NOT NULL,
    raw_list_text TEXT NOT NULL,
    raw_detail_text TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    last_fetched_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    last_verified_at TIMESTAMP WITHOUT TIME ZONE,
    freshness_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (source_name, source_category, canonical_key)
);

CREATE INDEX ix_external_source_records_source_name ON external_source_records (source_name);

CREATE INDEX ix_external_source_records_source_category ON external_source_records (source_category);

CREATE INDEX ix_external_source_records_external_id ON external_source_records (external_id);

CREATE INDEX ix_external_source_records_canonical_key ON external_source_records (canonical_key);

CREATE INDEX ix_external_source_records_region ON external_source_records (region);

CREATE INDEX ix_external_source_records_status ON external_source_records (status);

CREATE INDEX ix_external_source_records_end_date ON external_source_records (end_date);

UPDATE alembic_version SET version_num='0010_external_source_records' WHERE alembic_version.version_num = '0009_add_trip_status';

-- Running upgrade 0010_external_source_records -> 0011_phone_verification_codes

CREATE TABLE phone_verification_codes (
    id BIGSERIAL NOT NULL,
    user_id BIGINT NOT NULL,
    phone_number VARCHAR(30) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    attempt_count INTEGER DEFAULT '0' NOT NULL,
    verified_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_phone_verification_codes_user_id ON phone_verification_codes (user_id);

CREATE INDEX ix_phone_verification_codes_phone_number ON phone_verification_codes (phone_number);

CREATE INDEX ix_phone_verification_codes_expires_at ON phone_verification_codes (expires_at);

UPDATE alembic_version SET version_num='0011_phone_verification_codes' WHERE alembic_version.version_num = '0010_external_source_records';

-- Running upgrade 0011_phone_verification_codes -> 0012_policy_source_tracking

ALTER TABLE policies ADD COLUMN source_type VARCHAR(50);

ALTER TABLE policies ADD COLUMN source_name VARCHAR(100);

ALTER TABLE policies ADD COLUMN source_category VARCHAR(80);

ALTER TABLE policies ADD COLUMN external_source_record_id BIGINT;

ALTER TABLE policies ADD COLUMN source_url VARCHAR(500);

ALTER TABLE policies ADD COLUMN source_canonical_key VARCHAR(160);

ALTER TABLE policies ADD COLUMN normalized_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE policies ADD COLUMN last_verified_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE policies ADD COLUMN verification_status VARCHAR(30);

ALTER TABLE policies ADD CONSTRAINT fk_policies_external_source_record_id_external_source_records FOREIGN KEY(external_source_record_id) REFERENCES external_source_records (id) ON DELETE SET NULL;

CREATE INDEX ix_policies_source_type ON policies (source_type);

CREATE INDEX ix_policies_source_name ON policies (source_name);

CREATE INDEX ix_policies_source_category ON policies (source_category);

CREATE UNIQUE INDEX ix_policies_external_source_record_id ON policies (external_source_record_id);

CREATE INDEX ix_policies_source_canonical_key ON policies (source_canonical_key);

UPDATE alembic_version SET version_num='0012_policy_source_tracking' WHERE alembic_version.version_num = '0011_phone_verification_codes';

-- Running upgrade 0012_policy_source_tracking -> 0013_add_trip_travel_area_id

ALTER TABLE trips ADD COLUMN travel_area_id VARCHAR(120);

CREATE INDEX ix_trips_travel_area_id ON trips (travel_area_id);

UPDATE alembic_version SET version_num='0013_add_trip_travel_area_id' WHERE alembic_version.version_num = '0012_policy_source_tracking';

-- Running upgrade 0013_add_trip_travel_area_id -> 0014_add_trip_participant_count

ALTER TABLE trips ADD COLUMN participant_count INTEGER DEFAULT '1' NOT NULL;

UPDATE alembic_version SET version_num='0014_add_trip_participant_count' WHERE alembic_version.version_num = '0013_add_trip_travel_area_id';

-- Running upgrade 0014_add_trip_participant_count -> 0015_admin_management_foundation

ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL;

ALTER TABLE users ADD CONSTRAINT ck_users_role_user_admin CHECK (role IN ('user', 'admin'));

ALTER TABLE policies ADD COLUMN status VARCHAR(20) DEFAULT 'active' NOT NULL;

ALTER TABLE policies ADD CONSTRAINT ck_policies_status_active_hidden CHECK (status IN ('active', 'hidden'));

ALTER TABLE policies ADD COLUMN admin_override_enabled BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE policies ADD COLUMN updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL;

CREATE TABLE admin_audit_logs (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY,
    admin_user_id BIGINT NOT NULL,
    action VARCHAR(80) NOT NULL,
    target_type VARCHAR(40) NOT NULL,
    target_id VARCHAR(120) NOT NULL,
    summary VARCHAR(300),
    before_json JSONB,
    after_json JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(admin_user_id) REFERENCES users (id)
);

CREATE INDEX ix_admin_audit_logs_admin_user_id ON admin_audit_logs (admin_user_id);

CREATE INDEX ix_admin_audit_logs_action ON admin_audit_logs (action);

CREATE INDEX ix_admin_audit_logs_target_type ON admin_audit_logs (target_type);

CREATE INDEX ix_admin_audit_logs_target_id ON admin_audit_logs (target_id);

UPDATE alembic_version SET version_num='0015_admin_management_foundation' WHERE alembic_version.version_num = '0014_add_trip_participant_count';

-- Running upgrade 0015_admin_management_foundation -> 0016_kakao_place_metadata

ALTER TABLE trip_places ADD COLUMN source_provider VARCHAR(40);

ALTER TABLE trip_places ADD COLUMN external_place_id VARCHAR(80);

ALTER TABLE trip_places ADD COLUMN category_group_code VARCHAR(20);

ALTER TABLE trip_places ADD COLUMN category_group_name VARCHAR(80);

ALTER TABLE trip_places ADD COLUMN place_url VARCHAR(500);

CREATE INDEX ix_trip_places_external_place_id ON trip_places (external_place_id);

UPDATE alembic_version SET version_num='0016_kakao_place_metadata' WHERE alembic_version.version_num = '0015_admin_management_foundation';

-- Running upgrade 0016_kakao_place_metadata -> 0017_widen_social_provider_id

ALTER TABLE social_accounts ALTER COLUMN provider_id TYPE VARCHAR(255);

UPDATE alembic_version SET version_num='0017_widen_social_provider_id' WHERE alembic_version.version_num = '0016_kakao_place_metadata';

-- Running upgrade 0017_widen_social_provider_id -> 0018_add_trip_revision

ALTER TABLE trips ADD COLUMN revision INTEGER DEFAULT 1 NOT NULL;

UPDATE alembic_version SET version_num='0018_add_trip_revision' WHERE alembic_version.version_num = '0017_widen_social_provider_id';

-- Running upgrade 0018_add_trip_revision -> 0019_email_first_signup

CREATE TABLE IF NOT EXISTS pending_signups (
            id BIGSERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
            expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        );

ALTER TABLE pending_signups DROP COLUMN IF EXISTS password_hash;

CREATE INDEX IF NOT EXISTS ix_pending_signups_email ON pending_signups (email);

CREATE INDEX IF NOT EXISTS ix_pending_signups_token_hash ON pending_signups (token_hash);

UPDATE alembic_version SET version_num='0019_email_first_signup' WHERE alembic_version.version_num = '0018_add_trip_revision';

-- Running upgrade 0019_email_first_signup -> 0020_oauth_onboarding_state

ALTER TABLE users
        ADD COLUMN IF NOT EXISTS nickname_setup_completed BOOLEAN NOT NULL DEFAULT true;

ALTER TABLE users
        ADD COLUMN IF NOT EXISTS profile_setup_skipped BOOLEAN NOT NULL DEFAULT false;

UPDATE alembic_version SET version_num='0020_oauth_onboarding_state' WHERE alembic_version.version_num = '0019_email_first_signup';

-- Running upgrade 0020_oauth_onboarding_state -> 0021_legacy_social_nickname

UPDATE users
        SET nickname_setup_completed = false
        WHERE onboarding_completed = false
          AND EXISTS (
              SELECT 1
              FROM social_accounts
              WHERE social_accounts.user_id = users.id
          );

UPDATE alembic_version SET version_num='0021_legacy_social_nickname' WHERE alembic_version.version_num = '0020_oauth_onboarding_state';

-- Running upgrade 0021_legacy_social_nickname -> 0022_signup_terms_agreements

ALTER TABLE users ADD COLUMN terms_accepted BOOLEAN DEFAULT 'false' NOT NULL;

ALTER TABLE users ADD COLUMN terms_accepted_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE users ADD COLUMN terms_version VARCHAR(32);

ALTER TABLE users ADD COLUMN privacy_accepted BOOLEAN DEFAULT 'false' NOT NULL;

ALTER TABLE users ADD COLUMN privacy_accepted_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE users ADD COLUMN privacy_version VARCHAR(32);

ALTER TABLE pending_signups ADD COLUMN terms_accepted BOOLEAN DEFAULT 'false' NOT NULL;

ALTER TABLE pending_signups ADD COLUMN terms_accepted_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE pending_signups ADD COLUMN terms_version VARCHAR(32);

ALTER TABLE pending_signups ADD COLUMN privacy_accepted BOOLEAN DEFAULT 'false' NOT NULL;

ALTER TABLE pending_signups ADD COLUMN privacy_accepted_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE pending_signups ADD COLUMN privacy_version VARCHAR(32);

CREATE TABLE pending_social_signups (
    id BIGSERIAL NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    email_verified BOOLEAN DEFAULT 'false' NOT NULL,
    nickname VARCHAR(100),
    redirect_path VARCHAR(500) DEFAULT '/home' NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (provider, provider_id),
    UNIQUE (token_hash)
);

CREATE INDEX ix_pending_social_signups_token_hash ON pending_social_signups (token_hash);

UPDATE alembic_version SET version_num='0022_signup_terms_agreements' WHERE alembic_version.version_num = '0021_legacy_social_nickname';

-- Running upgrade 0022_signup_terms_agreements -> 0023_policy_structured_detail

ALTER TABLE policies ADD COLUMN structured_detail JSONB;

UPDATE policies
            SET structured_detail = jsonb_build_object(
                'benefits', CASE
                    WHEN NULLIF(BTRIM(COALESCE(benefit_detail, policy_comment, description, '')), '') IS NULL THEN '[]'::jsonb
                    ELSE jsonb_build_array(jsonb_strip_nulls(jsonb_build_object(
                        'title', '혜택',
                        'description', NULLIF(BTRIM(COALESCE(benefit_detail, policy_comment, description)), ''),
                        'amount', NULLIF(BTRIM(benefit_detail), '')
                    )))
                END,
                'conditions', '[]'::jsonb,
                'periods', CASE
                    WHEN NULLIF(BTRIM(COALESCE(policy_period, '')), '') IS NOT NULL THEN jsonb_build_array(jsonb_build_object(
                        'title', '기간',
                        'description', BTRIM(policy_period)
                    ))
                    WHEN start_date IS NOT NULL OR end_date IS NOT NULL THEN jsonb_build_array(jsonb_strip_nulls(jsonb_build_object(
                        'title', '신청 기간',
                        'description', CONCAT_WS(' ~ ', start_date::text, end_date::text),
                        'startDate', start_date::text,
                        'endDate', end_date::text
                    )))
                    ELSE '[]'::jsonb
                END,
                'links', (
                    SELECT COALESCE(jsonb_agg(link_item), '[]'::jsonb)
                    FROM (
                        SELECT jsonb_build_object('label', '신청하기', 'url', apply_url) AS link_item
                        WHERE NULLIF(BTRIM(COALESCE(apply_url, '')), '') IS NOT NULL
                        UNION ALL
                        SELECT jsonb_build_object('label', '공식 안내', 'url', official_url) AS link_item
                        WHERE NULLIF(BTRIM(COALESCE(official_url, '')), '') IS NOT NULL
                          AND COALESCE(official_url, '') <> COALESCE(apply_url, '')
                    ) links
                ),
                'documents', (
                    SELECT COALESCE(jsonb_agg(jsonb_build_object('title', '필요 서류', 'description', pd.document_name) ORDER BY pd.id), '[]'::jsonb)
                    FROM policy_documents pd
                    WHERE pd.policy_id = policies.id
                      AND NULLIF(BTRIM(COALESCE(pd.document_name, '')), '') IS NOT NULL
                ),
                'notices', CASE
                    WHEN NULLIF(BTRIM(COALESCE(policy_comment, '')), '') IS NOT NULL
                         AND COALESCE(policy_comment, '') <> COALESCE(benefit_detail, '') THEN jsonb_build_array(jsonb_build_object(
                        'title', '확인 필요 사항',
                        'description', BTRIM(policy_comment)
                    ))
                    ELSE '[]'::jsonb
                END
            )
            WHERE structured_detail IS NULL;

UPDATE alembic_version SET version_num='0023_policy_structured_detail' WHERE alembic_version.version_num = '0022_signup_terms_agreements';

-- Running upgrade 0023_policy_structured_detail -> 0024_local_kst_time_shift

SELECT
        'before/after review: users.updated_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(updated_at) AS min_value,
        MAX(updated_at) AS max_value
    FROM users
    WHERE updated_at IS NOT NULL;

SELECT
        'before/after review: user_notification_settings.created_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(created_at) AS min_value,
        MAX(created_at) AS max_value
    FROM user_notification_settings
    WHERE created_at IS NOT NULL;

SELECT
        'before/after review: user_notification_settings.updated_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(updated_at) AS min_value,
        MAX(updated_at) AS max_value
    FROM user_notification_settings
    WHERE updated_at IS NOT NULL;

SELECT
        'before/after review: notification_deliveries.scheduled_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(scheduled_at) AS min_value,
        MAX(scheduled_at) AS max_value
    FROM notification_deliveries
    WHERE scheduled_at IS NOT NULL;

SELECT
        'before/after review: notification_deliveries.updated_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(updated_at) AS min_value,
        MAX(updated_at) AS max_value
    FROM notification_deliveries
    WHERE updated_at IS NOT NULL;

SELECT
        'before/after review: external_source_records.last_fetched_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(last_fetched_at) AS min_value,
        MAX(last_fetched_at) AS max_value
    FROM external_source_records
    WHERE last_fetched_at IS NOT NULL;

SELECT
        'before/after review: external_source_records.last_verified_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(last_verified_at) AS min_value,
        MAX(last_verified_at) AS max_value
    FROM external_source_records
    WHERE last_verified_at IS NOT NULL;

UPDATE "users" SET "updated_at" = "updated_at" + INTERVAL '9 hours' WHERE "updated_at" IS NOT NULL;

UPDATE "user_notification_settings" SET "created_at" = "created_at" + INTERVAL '9 hours' WHERE "created_at" IS NOT NULL;

UPDATE "user_notification_settings" SET "updated_at" = "updated_at" + INTERVAL '9 hours' WHERE "updated_at" IS NOT NULL;

UPDATE "notification_deliveries" SET "scheduled_at" = "scheduled_at" + INTERVAL '9 hours' WHERE "scheduled_at" IS NOT NULL;

UPDATE "notification_deliveries" SET "updated_at" = "updated_at" + INTERVAL '9 hours' WHERE "updated_at" IS NOT NULL;

UPDATE "external_source_records" SET "last_fetched_at" = "last_fetched_at" + INTERVAL '9 hours' WHERE "last_fetched_at" IS NOT NULL;

UPDATE "external_source_records" SET "last_verified_at" = "last_verified_at" + INTERVAL '9 hours' WHERE "last_verified_at" IS NOT NULL;

SELECT
        'before/after review: users.updated_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(updated_at) AS min_value,
        MAX(updated_at) AS max_value
    FROM users
    WHERE updated_at IS NOT NULL;

SELECT
        'before/after review: user_notification_settings.created_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(created_at) AS min_value,
        MAX(created_at) AS max_value
    FROM user_notification_settings
    WHERE created_at IS NOT NULL;

SELECT
        'before/after review: user_notification_settings.updated_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(updated_at) AS min_value,
        MAX(updated_at) AS max_value
    FROM user_notification_settings
    WHERE updated_at IS NOT NULL;

SELECT
        'before/after review: notification_deliveries.scheduled_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(scheduled_at) AS min_value,
        MAX(scheduled_at) AS max_value
    FROM notification_deliveries
    WHERE scheduled_at IS NOT NULL;

SELECT
        'before/after review: notification_deliveries.updated_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(updated_at) AS min_value,
        MAX(updated_at) AS max_value
    FROM notification_deliveries
    WHERE updated_at IS NOT NULL;

SELECT
        'before/after review: external_source_records.last_fetched_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(last_fetched_at) AS min_value,
        MAX(last_fetched_at) AS max_value
    FROM external_source_records
    WHERE last_fetched_at IS NOT NULL;

SELECT
        'before/after review: external_source_records.last_verified_at' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN(last_verified_at) AS min_value,
        MAX(last_verified_at) AS max_value
    FROM external_source_records
    WHERE last_verified_at IS NOT NULL;

UPDATE alembic_version SET version_num='0024_local_kst_time_shift' WHERE alembic_version.version_num = '0023_policy_structured_detail';

COMMIT;
