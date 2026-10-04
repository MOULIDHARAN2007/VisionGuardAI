"""
VisionGuard AI 2.0 - Database Connection & Initialization
Handles SQLite engine, Session management, and initial data seeding.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base, User, Worker, Admin, Supervisor, UserRole

# Database path relative to project root
DB_PATH = Path(__file__).resolve().parent.parent / "visionguard.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency that yields a database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_initial_data(db: Session):
    """Seed initial demo accounts for Admin, Supervisor, Worker, and User if not already present."""
    # Import hashing function inside to prevent circular dependency
    from auth.auth import get_password_hash

    # 1. Seed Admin
    admin_user = db.query(User).filter(User.email == "admin@visionguard.ai").first()
    if not admin_user:
        admin_user = User(
            full_name="System Administrator",
            email="admin@visionguard.ai",
            phone="+1-555-0100",
            password_hash=get_password_hash("AdminPassword123!"),
            role=UserRole.ADMIN.value,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        admin_profile = Admin(user_id=admin_user.id)
        db.add(admin_profile)
        db.commit()
        print("[Database Seed] Created initial Admin account: admin@visionguard.ai")

    # 2. Seed Supervisor (Field Supervisor)
    supervisor_user = db.query(User).filter(User.email == "supervisor@visionguard.ai").first()
    if not supervisor_user:
        supervisor_user = User(
            full_name="Field Supervisor Marcus",
            email="supervisor@visionguard.ai",
            phone="+1-555-0120",
            password_hash=get_password_hash("SupervisorPassword123!"),
            role=UserRole.SUPERVISOR.value,
            is_active=True
        )
        db.add(supervisor_user)
        db.commit()
        db.refresh(supervisor_user)

        supervisor_profile = Supervisor(
            user_id=supervisor_user.id,
            employee_id="VG-SUP-001",
            department="Municipal Field Inspection & Quality Control",
            phone="+1-555-0120",
            specialization="Structural & Surface Inspection",
            zone="Central Zone",
            approval_status="APPROVED",
            is_active=True
        )
        db.add(supervisor_profile)
        db.commit()
        print("[Database Seed] Created initial Supervisor account: supervisor@visionguard.ai")

    # 3. Seed Worker
    worker_user = db.query(User).filter(User.email == "worker@visionguard.ai").first()
    if not worker_user:
        worker_user = User(
            full_name="Field Engineer Alex",
            email="worker@visionguard.ai",
            phone="+1-555-0150",
            password_hash=get_password_hash("WorkerPassword123!"),
            role=UserRole.WORKER.value,
            is_active=True
        )
        db.add(worker_user)
        db.commit()
        db.refresh(worker_user)

        worker_profile = Worker(
            user_id=worker_user.id,
            employee_id="VG-ENG-001",
            department="Road & Infrastructure Maintenance",
            phone="+1-555-0150",
            specialization="Pothole Repair & Surface Diagnostics",
            is_active=True
        )
        db.add(worker_profile)
        db.commit()
        print("[Database Seed] Created initial Worker account: worker@visionguard.ai")

    # 4. Seed User
    demo_user = db.query(User).filter(User.email == "user@visionguard.ai").first()
    if not demo_user:
        demo_user = User(
            full_name="Jane Citizen",
            email="user@visionguard.ai",
            phone="+1-555-0199",
            password_hash=get_password_hash("UserPassword123!"),
            role=UserRole.USER.value,
            is_active=True
        )
        db.add(demo_user)
        db.commit()
        print("[Database Seed] Created initial User account: user@visionguard.ai")


def init_db():
    """Create all database tables and seed initial demo data."""
    print(f"[Database] Initializing SQLite database at: {DB_PATH} ...")
    Base.metadata.create_all(bind=engine)
    
    # Safe SQLite column migration for new columns
    with engine.connect() as conn:
        try:
            # Check existing columns in detections table
            res = conn.exec_driver_sql("PRAGMA table_info(detections)").fetchall()
            existing_cols = [r[1] for r in res]
            if "source_type" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE detections ADD COLUMN source_type VARCHAR(30) DEFAULT 'IMAGE' NOT NULL")
                print("[Database] Migrated column 'source_type' to detections table.")
            if "video_path" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE detections ADD COLUMN video_path VARCHAR(255)")
                print("[Database] Migrated column 'video_path' to detections table.")
            # Check existing columns in complaints table
            res_cmp = conn.exec_driver_sql("PRAGMA table_info(complaints)").fetchall()
            existing_cmp_cols = [r[1] for r in res_cmp]
            if "risk_score" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN risk_score FLOAT DEFAULT 0.0")
                print("[Database] Migrated column 'risk_score' to complaints table.")
            if "risk_level" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN risk_level VARCHAR(20) DEFAULT 'LOW'")
                print("[Database] Migrated column 'risk_level' to complaints table.")
            if "priority_level" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN priority_level VARCHAR(20) DEFAULT 'NORMAL'")
                print("[Database] Migrated column 'priority_level' to complaints table.")
            if "risk_factors" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN risk_factors TEXT")
                print("[Database] Migrated column 'risk_factors' to complaints table.")
            if "risk_calculated_at" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN risk_calculated_at DATETIME")
                print("[Database] Migrated column 'risk_calculated_at' to complaints table.")
            if "source" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN source VARCHAR(50) DEFAULT 'CITIZEN_IMAGE'")
                print("[Database] Migrated column 'source' to complaints table.")
            if "annotated_image_path" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN annotated_image_path VARCHAR(255)")
                print("[Database] Migrated column 'annotated_image_path' to complaints table.")
            if "camera_id" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN camera_id VARCHAR(100)")
                print("[Database] Migrated column 'camera_id' to complaints table.")
            if "assigned_supervisor_id" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN assigned_supervisor_id INTEGER REFERENCES supervisors(id) ON DELETE SET NULL")
                print("[Database] Migrated column 'assigned_supervisor_id' to complaints table.")
            if "supervisor_notes" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN supervisor_notes TEXT")
                print("[Database] Migrated column 'supervisor_notes' to complaints table.")
            if "supervisor_validated_at" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN supervisor_validated_at DATETIME")
                print("[Database] Migrated column 'supervisor_validated_at' to complaints table.")
            if "supervisor_recommendation" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN supervisor_recommendation VARCHAR(50)")
                print("[Database] Migrated column 'supervisor_recommendation' to complaints table.")
            if "supervisor_recommended_at" not in existing_cmp_cols:
                conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN supervisor_recommended_at DATETIME")
                print("[Database] Migrated column 'supervisor_recommended_at' to complaints table.")
            
            # Check existing columns in workers table
            res_wrk = conn.exec_driver_sql("PRAGMA table_info(workers)").fetchall()
            existing_wrk_cols = [r[1] for r in res_wrk]
            if "approval_status" not in existing_wrk_cols:
                conn.exec_driver_sql("ALTER TABLE workers ADD COLUMN approval_status VARCHAR(30) DEFAULT 'APPROVED' NOT NULL")
                print("[Database] Migrated column 'approval_status' to workers table.")
            if "approved_at" not in existing_wrk_cols:
                conn.exec_driver_sql("ALTER TABLE workers ADD COLUMN approved_at DATETIME")
                print("[Database] Migrated column 'approved_at' to workers table.")
            if "approved_by" not in existing_wrk_cols:
                conn.exec_driver_sql("ALTER TABLE workers ADD COLUMN approved_by INTEGER")
                print("[Database] Migrated column 'approved_by' to workers table.")
            if "rejection_reason" not in existing_wrk_cols:
                conn.exec_driver_sql("ALTER TABLE workers ADD COLUMN rejection_reason VARCHAR(255)")
                print("[Database] Migrated column 'rejection_reason' to workers table.")
            
            # Check existing columns in supervisors table if needed
            res_sup = conn.exec_driver_sql("PRAGMA table_info(supervisors)").fetchall()
            existing_sup_cols = [r[1] for r in res_sup]
            if "approval_status" not in existing_sup_cols:
                conn.exec_driver_sql("ALTER TABLE supervisors ADD COLUMN approval_status VARCHAR(30) DEFAULT 'APPROVED' NOT NULL")
                print("[Database] Migrated column 'approval_status' to supervisors table.")
            if "approved_at" not in existing_sup_cols:
                conn.exec_driver_sql("ALTER TABLE supervisors ADD COLUMN approved_at DATETIME")
                print("[Database] Migrated column 'approved_at' to supervisors table.")
            if "approved_by" not in existing_sup_cols:
                conn.exec_driver_sql("ALTER TABLE supervisors ADD COLUMN approved_by INTEGER")
                print("[Database] Migrated column 'approved_by' to supervisors table.")
            if "rejection_reason" not in existing_sup_cols:
                conn.exec_driver_sql("ALTER TABLE supervisors ADD COLUMN rejection_reason VARCHAR(255)")
                print("[Database] Migrated column 'rejection_reason' to supervisors table.")
        except Exception as e:
            print(f"[Database Migration Warning] {e}")

    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
    print("[Database] Database initialized and verified successfully!")


if __name__ == "__main__":
    init_db()
