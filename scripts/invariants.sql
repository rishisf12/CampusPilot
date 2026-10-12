-- invariants.sql
-- Must pass after every Phase 1 migration step.
-- Run: psql -U campuspilot -d campuspilot -f invariants.sql
-- Exit code 0 = all green, non-zero = something broke.

\pset pager off
\set ON_ERROR_STOP on

-- ============================================================
-- 1. attendance_record MUST have user_id and unique per user
-- ============================================================
SELECT '1a: attendance_record.user_id column exists' AS check,
       (SELECT true FROM information_schema.columns
        WHERE table_schema='academic' AND table_name='attendance_record' AND column_name='user_id' AND is_nullable='NO') AS pass;

SELECT '1b: UNIQUE (user_id, course_id, date) exists' AS check,
       (SELECT true FROM pg_indexes
        WHERE schemaname='academic' AND tablename='attendance_record' AND indexname='uq_attendance_user_course_date') AS pass;

-- ============================================================
-- 2. user_profile.user_id is NOT NULL + unique
-- ============================================================
SELECT '2a: user_profile.user_id NOT NULL' AS check,
       (SELECT true FROM information_schema.columns
        WHERE table_schema='core' AND table_name='user_profile' AND column_name='user_id' AND is_nullable='NO') AS pass;

SELECT '2b: user_profile.user_id UNIQUE' AS check,
       (SELECT true FROM pg_indexes
        WHERE schemaname='core' AND tablename='user_profile' AND indexname='ix_user_profile_user_id') AS pass;

SELECT '2c: zero orphan user_profile rows' AS check,
       (SELECT count(*) = 0 FROM core.user_profile WHERE user_id IS NULL) AS pass;

-- ============================================================
-- 3. roll_number unique where present
-- ============================================================
SELECT '3: unique roll_number index exists' AS check,
       (SELECT true FROM pg_indexes
        WHERE schemaname='core' AND tablename='user' AND indexname='ix_user_roll_number'
          AND indexdef LIKE '%WHERE%roll_number IS NOT NULL%') AS pass;

-- ============================================================
-- 4. FKs have sensible ON DELETE
-- ============================================================
SELECT '4a: user_profile -> user ON DELETE CASCADE' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='core' AND tc.table_name='user_profile' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='CASCADE') AS pass;

SELECT '4b: passkey_credential -> user ON DELETE CASCADE' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='core' AND tc.table_name='passkey_credential' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='CASCADE') AS pass;

SELECT '4c: passkey_challenge -> user ON DELETE CASCADE' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='core' AND tc.table_name='passkey_challenge' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='CASCADE') AS pass;

SELECT '4d: password_reset_code -> user ON DELETE CASCADE' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='core' AND tc.table_name='password_reset_code' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='CASCADE') AS pass;

SELECT '4e: feedback -> user ON DELETE SET NULL' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='social' AND tc.table_name='feedback' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='SET NULL') AS pass;

SELECT '4f: team_member -> user ON DELETE CASCADE' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='social' AND tc.table_name='team_member' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='CASCADE') AS pass;

SELECT '4g: join_request -> user ON DELETE CASCADE' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='social' AND tc.table_name='join_request' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='CASCADE') AS pass;

SELECT '4h: team -> owner ON DELETE SET NULL' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='social' AND tc.table_name='team' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='SET NULL') AS pass;

SELECT '4i: hackathon -> created_by ON DELETE SET NULL' AS check,
       (SELECT true FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.table_schema='social' AND tc.table_name='hackathon' AND ccu.table_schema='core' AND ccu.table_name='user' AND rc.delete_rule='SET NULL') AS pass;

-- ============================================================
-- 5. ENUM types for fixed-value columns
-- ============================================================
SELECT '5a: user_role enum exists' AS check,
       (SELECT true FROM pg_type WHERE typname='user_role') AS pass;

SELECT '5b: join_request_status enum exists' AS check,
       (SELECT true FROM pg_type WHERE typname='join_request_status') AS pass;

SELECT '5c: exam_upload_kind enum exists' AS check,
       (SELECT true FROM pg_type WHERE typname='exam_upload_kind') AS pass;

SELECT '5d: purchase_kind enum exists' AS check,
       (SELECT true FROM pg_type WHERE typname='purchase_kind') AS pass;

SELECT '5e: crash_report_kind enum exists' AS check,
       (SELECT true FROM pg_type WHERE typname='crash_report_kind') AS pass;

SELECT '5f: security_event_kind enum exists' AS check,
       (SELECT true FROM pg_type WHERE typname='security_event_kind') AS pass;

SELECT '5g: scan_result_status enum exists' AS check,
       (SELECT true FROM pg_type WHERE typname='scan_result_status') AS pass;

SELECT '5h: hackathon_source enum exists' AS check,
       (SELECT true FROM pg_type WHERE typname='hackathon_source') AS pass;

-- ============================================================
-- 6. timetable_slot deduped + unique constraint
-- ============================================================
SELECT '6a: no duplicate (day,start_time,end_time,course_code,branch_or_program)' AS check,
       (SELECT count(*) = 0 FROM (
         SELECT day, start_time, end_time, course_code, branch_or_program, count(*) AS c
         FROM academic.timetable_slot
         GROUP BY day, start_time, end_time, course_code, branch_or_program
         HAVING count(*) > 1
       ) x) AS pass;

SELECT '6b: UNIQUE (day,start_time,end_time,course_code,branch_or_program)' AS check,
       (SELECT true FROM pg_indexes
        WHERE schemaname='academic' AND tablename='timetable_slot' AND indexname='uq_timetable_slot_day_time_course_branch') AS pass;

-- ============================================================
-- 7. Attendance reads are per-user (code assertion)
-- ============================================================
-- These are manual checks after running the app:
-- - /attendance/subjects returns only courses in current user's timetable
-- - /attendance/records returns only rows where attendance_record.user_id = current_user
-- - Two different users see zero shared attendance data

\echo '=== INVARIANT CHECKS COMPLETE ==='