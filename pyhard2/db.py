"""Database and tables used to store the hardware log.

Use SQLAlchemy.

"""
from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class LogTable(Base):

    """Table storing the hardware log.

    .. table:: Example.

        ========== ==== ======== ========================== =====
        controller node command  timestamp                  value
        ========== ==== ======== ========================== =====
        ...        ...  ...      ...                        ...
        Watlow     1    Setpoint 2015-03-01 11:40:29.123456 100.0
        Watlow     1    Measure  2015-03-01 11:40:32.789012  80.0
        Watlow     1    Measure  2015-03-01 11:40:37.345678 112.0
        ...        ...  ...      ...                        ...
        ========== ==== ======== ========================== =====

    """
    __tablename__ = "logtable"
    id = Column(Integer, primary_key=True)
    controller = Column(String)
    node = Column(String)
    command = Column(String)
    timestamp = Column(DateTime)
    value = Column(Float)


def get_session(url="sqlite:///"):
    """Initialize and return a session."""
    session = sessionmaker()
    connection = create_engine(url)
    session.configure(bind=connection)
    Base.metadata.create_all(connection)
    return session()


if __name__ == "__main__":
    from datetime import datetime, timedelta

    s = get_session("sqlite:///pyhard2.db")
    log = LogTable(
        controller="ctrlr",
        node=1,
        command="cmd",
        timestamp=datetime.utcnow(),
        value=12,
    )
    s.add(log)
    s.commit()

    q = s.query(LogTable).filter(
        LogTable.timestamp >= datetime.utcnow() - timedelta(minutes=5))

    for id, cmd, t in ((__.id, __.command, __.timestamp) for __ in q.all()):
        print(id, cmd, t)

    s.close()
