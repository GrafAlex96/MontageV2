from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime

Base = declarative_base()

class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("Job", back_populates="user")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    target_duration = Column(Integer)  # in seconds: 15, 30, 45, 60
    progress = Column(Float, default=0.0)
    error_message = Column(String, nullable=True)
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
