CREATE TABLE activation_codes (
    code TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    tier TEXT NOT NULL,  -- 'self_check', 'admin_check', 'premium'
    is_used BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    used_at DATETIME,
    used_by INTEGER,
    FOREIGN KEY(used_by) REFERENCES users(user_id)
);

CREATE TABLE courses (
    course_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    config JSON NOT NULL
);

CREATE TABLE user_courses (
    user_id INTEGER,
    course_id TEXT,
    tier TEXT NOT NULL,
    activated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(course_id) REFERENCES courses(course_id),
    PRIMARY KEY(user_id, course_id)
);