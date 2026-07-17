INFO  [alembic.runtime.migration] Context impl MySQLImpl.
INFO  [alembic.runtime.migration] Generating static SQL
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INFO  [alembic.runtime.migration] Running upgrade  -> 20260717_01, EEG collection foundation.
-- Running upgrade  -> 20260717_01

CREATE TABLE dataset_participants (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    participant_code VARCHAR(20) NOT NULL, 
    consent_confirmed_at DATETIME NOT NULL, 
    state ENUM('active','withdrawn') NOT NULL, 
    withdrawn_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    UNIQUE (participant_code)
);

CREATE INDEX ix_dataset_participants_participant_code ON dataset_participants (participant_code);

CREATE TABLE emotion_stimuli (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    title VARCHAR(150) NOT NULL, 
    file_path VARCHAR(500) NOT NULL, 
    checksum VARCHAR(64) NOT NULL, 
    duration_seconds FLOAT NOT NULL, 
    target_quadrant ENUM('positive_low','positive_high','negative_low','negative_high') NOT NULL, 
    approval_state ENUM('draft','approved','retired') NOT NULL, 
    stimulus_set_version VARCHAR(30) NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    UNIQUE (checksum)
);

CREATE INDEX ix_emotion_stimuli_target_quadrant ON emotion_stimuli (target_quadrant);

CREATE TABLE dataset_versions (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    version VARCHAR(30) NOT NULL, 
    manifest_json TEXT NOT NULL, 
    manifest_checksum VARCHAR(64) NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    UNIQUE (version), 
    UNIQUE (manifest_checksum)
);

CREATE TABLE model_versions (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    version VARCHAR(30) NOT NULL, 
    dataset_version VARCHAR(30) NOT NULL, 
    artifact_path VARCHAR(500) NOT NULL, 
    artifact_checksum VARCHAR(64) NOT NULL, 
    metadata_json TEXT NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    UNIQUE (version), 
    UNIQUE (artifact_checksum)
);

CREATE TABLE collection_sessions (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    participant_id INTEGER NOT NULL, 
    device_id VARCHAR(100), 
    device_name VARCHAR(100), 
    eyes_open_baseline_path VARCHAR(500), 
    eyes_open_baseline_checksum VARCHAR(64), 
    eyes_closed_baseline_path VARCHAR(500), 
    eyes_closed_baseline_checksum VARCHAR(64), 
    completed_trials INTEGER NOT NULL, 
    total_trials INTEGER NOT NULL, 
    state ENUM('preparation','baseline','ready','in_progress','completed','interrupted','withdrawn','failed') NOT NULL, 
    started_at DATETIME, 
    completed_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    FOREIGN KEY(participant_id) REFERENCES dataset_participants (id)
);

CREATE INDEX ix_collection_sessions_participant_id ON collection_sessions (participant_id);

CREATE INDEX ix_collection_sessions_state ON collection_sessions (state);

CREATE TABLE collection_trials (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    session_id INTEGER NOT NULL, 
    stimulus_id INTEGER NOT NULL, 
    randomized_order INTEGER NOT NULL, 
    valence_rating INTEGER NOT NULL, 
    arousal_rating INTEGER NOT NULL, 
    confidence INTEGER NOT NULL, 
    valence_label BOOL, 
    arousal_label BOOL, 
    valid_valence_label BOOL NOT NULL, 
    valid_arousal_label BOOL NOT NULL, 
    qc_summary_json TEXT, 
    eeg_file_path VARCHAR(500) NOT NULL, 
    eeg_checksum VARCHAR(64) NOT NULL, 
    review_state ENUM('pending','accepted','rejected') NOT NULL, 
    started_at DATETIME, 
    completed_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_collection_trials_valence CHECK (valence_rating BETWEEN 1 AND 9), 
    CONSTRAINT ck_collection_trials_arousal CHECK (arousal_rating BETWEEN 1 AND 9), 
    CONSTRAINT ck_collection_trials_confidence CHECK (confidence BETWEEN 1 AND 5), 
    FOREIGN KEY(session_id) REFERENCES collection_sessions (id), 
    FOREIGN KEY(stimulus_id) REFERENCES emotion_stimuli (id)
);

CREATE INDEX ix_collection_trials_session_id ON collection_trials (session_id);

CREATE INDEX ix_collection_trials_stimulus_id ON collection_trials (stimulus_id);

CREATE INDEX ix_collection_trials_review_state ON collection_trials (review_state);

CREATE TABLE artifact_events (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    trial_id INTEGER NOT NULL, 
    event_type VARCHAR(50) NOT NULL, 
    start_seconds FLOAT NOT NULL, 
    duration_seconds FLOAT NOT NULL, 
    details_json TEXT, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    FOREIGN KEY(trial_id) REFERENCES collection_trials (id)
);

CREATE INDEX ix_artifact_events_trial_id ON artifact_events (trial_id);

INSERT INTO alembic_version (version_num) VALUES ('20260717_01');

