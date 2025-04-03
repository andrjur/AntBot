from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)
    name = Column(String)
    registration_date = Column(DateTime)
    tokens = Column(Integer)
    
    courses = relationship("UserCourse", back_populates="user")
    homeworks = relationship("Homework", back_populates="user")

class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(String, primary_key=True)
    name = Column(String)
    code = Column(String, unique=True)
    description = Column(String)
    created_at = Column(DateTime)

class UserCourse(Base):
    __tablename__ = 'user_courses'
    
    user_id = Column(Integer, ForeignKey('users.user_id'), primary_key=True)
    course_id = Column(String, ForeignKey('courses.id'), primary_key=True)
    version_id = Column(String)
    current_lesson = Column(Integer)
    activation_date = Column(DateTime)
    first_lesson_time = Column(DateTime)
    
    user = relationship("User", back_populates="courses")
    course = relationship("Course")

class Homework(Base):
    __tablename__ = 'homeworks'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    course_id = Column(String)
    lesson = Column(Integer)
    status = Column(String, default='pending')
    submission_time = Column(DateTime)
    file_id = Column(String)
    admin_id = Column(Integer)
    
    user = relationship("User", back_populates="homeworks")

class ScheduledFile(Base):
    """Модель для запланированных файлов (теперь не потеряется)"""
    __tablename__ = 'scheduled_files'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    course_id = Column(String, nullable=False)
    lesson = Column(Integer, nullable=False)
    file_name = Column(String, nullable=False)
    send_at = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False)