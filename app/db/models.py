from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime

Base = declarative_base()

class JobStatus(enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    ANALYZING = "ANALYZING"
    PROCESSING = "PROCESSING"
    RENDERING = "RENDERING"
    POST_PROCESSING = "POST_PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    storage_quota_bytes = Column(Integer, default=5 * 1024 * 1024 * 1024) # 5GB
    used_storage_bytes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("Job", back_populates="user")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    trace_id = Column(String, unique=True, index=True)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    target_duration = Column(Integer)  # in seconds: 15, 30, 45, 60
    progress = Column(Float, default=0.0)
    error_message = Column(String, nullable=True)
    error_category = Column(String, nullable=True) # critical, recoverable, warning
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="jobs")
    files = relationship("UploadedFile", back_populates="job")
    render = relationship("RenderHistory", back_populates="job", uselist=False)

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    file_path = Column(String)
    file_name = Column(String)
    file_size = Column(Integer)
    duration = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="files")

class RenderHistory(Base):
    __tablename__ = "render_history"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    output_path = Column(String)
    file_size = Column(Integer)
    duration = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="render")
