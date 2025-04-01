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

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_courses_course_lesson ON user_courses(course_id, current_lesson);
CREATE INDEX IF NOT EXISTS idx_homework_status ON homework(user_id, course_id, lesson, status);

-- Add homework tracking table
-- Create homework table
CREATE TABLE IF NOT EXISTS homeworks (
    hw_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id TEXT NOT NULL,
    lesson INTEGER NOT NULL,
    status TEXT CHECK(status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
    submission_time TIMESTAMP DEFAULT NULL,
    approval_time TIMESTAMP DEFAULT NULL,
    next_lesson_at TIMESTAMP DEFAULT NULL,
    admin_id INTEGER DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_homework_user ON homeworks(user_id);
CREATE INDEX IF NOT EXISTS idx_homework_status ON homeworks(status);
CREATE INDEX IF NOT EXISTS idx_homework_course ON homeworks(course_id, lesson);

-- Add course statistics table (for caching)
CREATE TABLE IF NOT EXISTS course_stats (
    course_id TEXT NOT NULL,
    lesson INTEGER NOT NULL,
    total_active INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    avg_completion_time INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (course_id, lesson)
);