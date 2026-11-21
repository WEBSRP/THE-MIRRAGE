"""Frozen 2026-11-20 schema: never import live models into historical revisions.

Do not edit this snapshot when models change; add a new Alembic revision instead.
"""
import sqlalchemy as sa

REVISIONS = ("20261120_0001", "20261120_0002", "20261120_0003", "20261120_0004")
REVISION_TABLES = {
    REVISIONS[0]: ("users", "challenges", "game_sessions", "vpn_profiles", "activity_logs", "flag_submissions", "otp_codes"),
    REVISIONS[1]: ("challenge_solves", "flag_submission_quotas"),
    REVISIONS[2]: ("vpn_address_reservations",),
    REVISIONS[3]: ("vpn_revocations", "vpn_crl_maintenance"),
}


def schema_at(revision):
    if revision not in REVISIONS:
        raise ValueError("Unknown frozen schema revision")
    metadata = sa.MetaData()
    sa.Table(
        'challenges',
        metadata,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('flag', sa.String(length=128), nullable=False),
        sa.Column('hint', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    sa.Index('ix_challenges_slug', metadata.tables['challenges'].c['slug'], unique=True)
    sa.Table(
        'users',
        metadata,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=True),
        sa.Column('email_verified', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    sa.Index('ix_users_email', metadata.tables['users'].c['email'], unique=True)
    sa.Index('ix_users_username', metadata.tables['users'].c['username'], unique=True)
    sa.Table(
        'vpn_crl_maintenance',
        metadata,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('next_check_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('claimed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('claim_token', sa.String(length=36), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    sa.Table(
        'vpn_revocations',
        metadata,
        sa.Column('client_name', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('requested_by', sa.String(length=36), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('claimed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('claim_token', sa.String(length=36), nullable=True),
        sa.Column('last_error', sa.String(length=64), nullable=True),
        sa.Column('certificate_pem', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('client_name'),
    )
    sa.Index('ix_vpn_revocations_user_id', metadata.tables['vpn_revocations'].c['user_id'], unique=False)
    sa.Table(
        'challenge_solves',
        metadata,
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('challenge_id', sa.String(length=36), nullable=False),
        sa.Column('solved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'challenge_id'),
    )
    sa.Table(
        'flag_submission_quotas',
        metadata,
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('window', sa.Integer(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )
    sa.Table(
        'flag_submissions',
        metadata,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('challenge_id', sa.String(length=36), nullable=False),
        sa.Column('submitted_flag', sa.String(length=128), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    sa.Index('ix_flag_submissions_challenge_id', metadata.tables['flag_submissions'].c['challenge_id'], unique=False)
    sa.Index('ix_flag_submissions_user_id', metadata.tables['flag_submissions'].c['user_id'], unique=False)
    sa.Table(
        'game_sessions',
        metadata,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'INITIALIZING', 'PROVISIONING', 'READY', 'STOPPING', 'TERMINATED', 'EXPIRED', 'ERROR', name='sessionstatus'), nullable=False),
        sa.Column('pod_name', sa.String(length=128), nullable=True),
        sa.Column('pod_namespace', sa.String(length=64), nullable=True),
        sa.Column('pod_ip', sa.String(length=45), nullable=True),
        sa.Column('mirage_ip', sa.String(length=45), nullable=True),
        sa.Column('ctf_ip', sa.String(length=45), nullable=True),
        sa.Column('player_vpn_ip', sa.String(length=45), nullable=True),
        sa.Column('mirage_port', sa.Integer(), nullable=False),
        sa.Column('ctf_port', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ready_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('terminated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    sa.Index('ix_game_sessions_status', metadata.tables['game_sessions'].c['status'], unique=False)
    sa.Index('ix_game_sessions_user_id', metadata.tables['game_sessions'].c['user_id'], unique=False)
    sa.Table(
        'otp_codes',
        metadata,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    sa.Index('ix_otp_codes_email', metadata.tables['otp_codes'].c['email'], unique=False)
    sa.Table(
        'vpn_address_reservations',
        metadata,
        sa.Column('address', sa.String(length=45), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('client_name', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('address'),
        sa.UniqueConstraint('client_name'),
        sa.UniqueConstraint('user_id'),
    )
    sa.Table(
        'vpn_profiles',
        metadata,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('client_name', sa.String(length=64), nullable=False),
        sa.Column('config_data', sa.Text(), nullable=False),
        sa.Column('assigned_ip', sa.String(length=45), nullable=True),
        sa.Column('is_connected', sa.Boolean(), nullable=False),
        sa.Column('bytes_received', sa.Integer(), nullable=False),
        sa.Column('bytes_sent', sa.Integer(), nullable=False),
        sa.Column('connected_since', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_name'),
    )
    sa.Index('ix_vpn_profiles_user_id', metadata.tables['vpn_profiles'].c['user_id'], unique=True)
    sa.Table(
        'activity_logs',
        metadata,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.Enum('SESSION_START', 'SESSION_STOP', 'VPN_CONNECT', 'VPN_DISCONNECT', 'SSH_AUTH_ATTEMPT', 'SSH_COMMAND', 'HONEYPOT_TRIGGER', 'DECEPTION_DISCOVERY', 'FLAG_SUBMISSION', name='activityeventtype'), nullable=False),
        sa.Column('summary', sa.String(length=255), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('source_ip', sa.String(length=45), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['game_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    sa.Index('ix_activity_logs_event_type', metadata.tables['activity_logs'].c['event_type'], unique=False)
    sa.Index('ix_activity_logs_session_id', metadata.tables['activity_logs'].c['session_id'], unique=False)
    sa.Index('ix_activity_logs_timestamp', metadata.tables['activity_logs'].c['timestamp'], unique=False)
    sa.Index('ix_activity_logs_user_id', metadata.tables['activity_logs'].c['user_id'], unique=False)
    selected = sa.MetaData()
    allowed = {name for key in REVISIONS[:REVISIONS.index(revision) + 1] for name in REVISION_TABLES[key]}
    for table in metadata.sorted_tables:
        if table.name in allowed:
            table.to_metadata(selected)
    return selected
